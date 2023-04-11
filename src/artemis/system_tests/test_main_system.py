import json
import threading
from dataclasses import dataclass
from sys import argv
from time import sleep
from typing import Any, Callable, Optional
from unittest.mock import MagicMock, patch

import pytest
from flask.testing import FlaskClient

from artemis.__main__ import Actions, BlueskyRunner, Status, cli_arg_parse, create_app
from artemis.experiment_plans.experiment_registry import PLAN_REGISTRY
from artemis.parameters import external_parameters

FGS_ENDPOINT = "/fast_grid_scan/"
START_ENDPOINT = FGS_ENDPOINT + Actions.START.value
STOP_ENDPOINT = Actions.STOP.value
STATUS_ENDPOINT = Actions.STATUS.value
SHUTDOWN_ENDPOINT = Actions.SHUTDOWN.value
TEST_PARAMS = json.dumps(external_parameters.from_file("test_parameters.json"))


class MockRunEngine:
    RE_takes_time = True
    aborting_takes_time = False
    error: Optional[str] = None

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        while self.RE_takes_time:
            sleep(0.1)
            if self.error:
                raise Exception(self.error)

    def abort(self):
        while self.aborting_takes_time:
            sleep(0.1)
            if self.error:
                raise Exception(self.error)
        self.RE_takes_time = False


@dataclass
class ClientAndRunEngine:
    client: FlaskClient
    mock_run_engine: MockRunEngine


def mock_dict_values(d: dict):
    return {k: MagicMock() for k, _ in d.items()}


TEST_EXPTS = {
    "test_experiment": {
        "setup": MagicMock(),
        "run": MagicMock(),
        "internal_param_type": MagicMock(),
        "experiment_param_type": MagicMock(),
    },
    "test_experiment_no_run": {
        "setup": MagicMock(),
        "internal_param_type": MagicMock(),
        "experiment_param_type": MagicMock(),
    },
    "test_experiment_no_internal_param_type": {
        "setup": MagicMock(),
        "run": MagicMock(),
        "experiment_param_type": MagicMock(),
    },
}


@pytest.fixture
def test_env():
    mock_run_engine = MockRunEngine()
    with patch.dict(
        "artemis.__main__.PLAN_REGISTRY",
        dict({k: mock_dict_values(v) for k, v in PLAN_REGISTRY.items()}, **TEST_EXPTS),
    ):
        app, runner = create_app({"TESTING": True}, mock_run_engine)
    runner_thread = threading.Thread(target=runner.wait_on_queue)
    runner_thread.start()
    with app.test_client() as client:
        with patch.dict(
            "artemis.__main__.PLAN_REGISTRY",
            dict(
                {k: mock_dict_values(v) for k, v in PLAN_REGISTRY.items()}, **TEST_EXPTS
            ),
        ):
            yield ClientAndRunEngine(client, mock_run_engine)

    runner.shutdown()
    runner_thread.join()


def wait_for_run_engine_status(
    client: FlaskClient,
    status_check: Callable[[str], bool] = lambda status: status != Status.BUSY.value,
    attempts=10,
):
    while attempts != 0:
        response = client.get(STATUS_ENDPOINT)
        response_json = json.loads(response.data)
        if status_check(response_json["status"]):
            return response_json
        else:
            attempts -= 1
            sleep(0.1)
    assert False, "Run engine still busy"


def check_status_in_response(response_object, expected_result: Status):
    response_json = json.loads(response_object.data)
    assert response_json["status"] == expected_result.value


def test_start_gives_success(test_env: ClientAndRunEngine):
    response = test_env.client.put(START_ENDPOINT, data=TEST_PARAMS)
    check_status_in_response(response, Status.SUCCESS)


def test_getting_status_return_idle(test_env: ClientAndRunEngine):
    response = test_env.client.get(STATUS_ENDPOINT)
    check_status_in_response(response, Status.IDLE)


def test_getting_status_after_start_sent_returns_busy(
    test_env: ClientAndRunEngine,
):
    test_env.client.put(START_ENDPOINT, data=TEST_PARAMS)
    response = test_env.client.get(STATUS_ENDPOINT)
    check_status_in_response(response, Status.BUSY)


def test_putting_bad_plan_fails(test_env: ClientAndRunEngine):
    response = test_env.client.put("/bad_plan/start", data=TEST_PARAMS).json
    assert isinstance(response, dict)
    assert response.get("status") == Status.FAILED.value
    assert (
        response.get("message")
        == "PlanNotFound(\"Experiment plan 'bad_plan' not found in registry.\")"
    )


def test_plan_with_no_params_fails(test_env: ClientAndRunEngine):
    response = test_env.client.put(
        "/test_experiment_no_internal_param_type/start", data=TEST_PARAMS
    ).json
    assert isinstance(response, dict)
    assert response.get("status") == Status.FAILED.value
    assert (
        response.get("message")
        == "PlanNotFound(\"Corresponing internal param type for 'test_experiment_no_internal_param_type' not found in registry.\")"
    )


def test_plan_with_no_run_fails(test_env: ClientAndRunEngine):
    response = test_env.client.put(
        "/test_experiment_no_run/start", data=TEST_PARAMS
    ).json
    assert isinstance(response, dict)
    assert response.get("status") == Status.FAILED.value
    assert (
        response.get("message")
        == "PlanNotFound(\"Experiment plan 'test_experiment_no_run' has no 'run' method.\")"
    )


def test_sending_start_twice_fails(test_env: ClientAndRunEngine):
    test_env.client.put(START_ENDPOINT, data=TEST_PARAMS)
    response = test_env.client.put(START_ENDPOINT, data=TEST_PARAMS)
    check_status_in_response(response, Status.FAILED)


def test_given_started_when_stopped_then_success_and_idle_status(
    test_env: ClientAndRunEngine,
):
    test_env.mock_run_engine.aborting_takes_time = True
    test_env.client.put(START_ENDPOINT, data=TEST_PARAMS)
    response = test_env.client.put(STOP_ENDPOINT)
    check_status_in_response(response, Status.ABORTING)
    response = test_env.client.get(STATUS_ENDPOINT)
    check_status_in_response(response, Status.ABORTING)
    test_env.mock_run_engine.aborting_takes_time = False
    wait_for_run_engine_status(
        test_env.client, lambda status: status != Status.ABORTING
    )
    check_status_in_response(response, Status.ABORTING)


def test_given_started_when_stopped_and_started_again_then_runs(
    test_env: ClientAndRunEngine,
):
    test_env.client.put(START_ENDPOINT, data=TEST_PARAMS)
    test_env.client.put(STOP_ENDPOINT)
    response = test_env.client.put(START_ENDPOINT, data=TEST_PARAMS)
    check_status_in_response(response, Status.SUCCESS)
    response = test_env.client.get(STATUS_ENDPOINT)
    check_status_in_response(response, Status.BUSY)


def test_given_started_when_RE_stops_on_its_own_with_error_then_error_reported(
    test_env: ClientAndRunEngine,
):
    test_env.client.put(START_ENDPOINT, data=TEST_PARAMS)
    error_message = "D'Oh"
    test_env.mock_run_engine.error = error_message
    response_json = wait_for_run_engine_status(test_env.client)
    assert response_json["status"] == Status.FAILED.value
    assert response_json["message"] == 'Exception("D\'Oh")'


def test_given_started_and_return_status_interrupted_when_RE_aborted_then_error_reported(
    test_env: ClientAndRunEngine,
):
    test_env.mock_run_engine.aborting_takes_time = True
    test_env.client.put(START_ENDPOINT, data=TEST_PARAMS)
    error_message = "D'Oh"
    test_env.client.put(STOP_ENDPOINT)
    test_env.mock_run_engine.error = error_message
    response_json = wait_for_run_engine_status(
        test_env.client, lambda status: status != Status.ABORTING.value
    )
    assert response_json["status"] == Status.FAILED.value
    assert response_json["message"] == 'Exception("D\'Oh")'


def test_given_started_when_RE_stops_on_its_own_happily_then_no_error_reported(
    test_env: ClientAndRunEngine,
):
    test_env.client.put(START_ENDPOINT, data=TEST_PARAMS)
    test_env.mock_run_engine.RE_takes_time = False
    response_json = wait_for_run_engine_status(test_env.client)
    assert response_json["status"] == Status.IDLE.value


def test_start_with_json_file_gives_success(test_env: ClientAndRunEngine):
    with open("test_parameters.json") as test_parameters_file:
        test_parameters_json = test_parameters_file.read()
    response = test_env.client.put(START_ENDPOINT, data=test_parameters_json)
    check_status_in_response(response, Status.SUCCESS)


def test_cli_args_parse():
    argv[1:] = ["--dev", "--logging-level=DEBUG"]
    test_args = cli_arg_parse()
    assert test_args == ("DEBUG", False, True, False)
    argv[1:] = ["--dev", "--logging-level=DEBUG", "--verbose-event-logging"]
    test_args = cli_arg_parse()
    assert test_args == ("DEBUG", True, True, False)
    argv[1:] = [
        "--dev",
        "--logging-level=DEBUG",
        "--verbose-event-logging",
        "--skip-startupconnection",
    ]
    test_args = cli_arg_parse()
    assert test_args == ("DEBUG", True, True, True)


@patch("dodal.i03.ApertureScatterguard")
@patch("dodal.i03.Backlight")
@patch("dodal.i03.EigerDetector")
@patch("dodal.i03.FastGridScan")
@patch("dodal.i03.S4SlitGaps")
@patch("dodal.i03.Smargon")
@patch("dodal.i03.Synchrotron")
@patch("dodal.i03.Undulator")
@patch("dodal.i03.Zebra")
@patch("artemis.experiment_plans.fast_grid_scan_plan.get_beamline_parameters")
@patch("dodal.i03.active_device_is_same_type")
def test_when_blueskyrunner_initiated_then_plans_are_setup_and_devices_connected(
    type_comparison,
    mock_get_beamline_params,
    zebra,
    undulator,
    synchrotron,
    smargon,
    s4_slits,
    fast_grid_scan,
    eiger,
    backlight,
    aperture_scatterguard,
):
    type_comparison.return_value = True
    BlueskyRunner(MagicMock(), skip_startup_connection=False)
    zebra.return_value.wait_for_connection.assert_called_once()
    undulator.return_value.wait_for_connection.assert_called_once()
    synchrotron.return_value.wait_for_connection.assert_called_once()
    smargon.return_value.wait_for_connection.assert_called_once()
    s4_slits.return_value.wait_for_connection.assert_called_once()
    fast_grid_scan.return_value.wait_for_connection.assert_called_once()
    eiger.return_value.wait_for_connection.assert_not_called()  # can't wait on eiger
    backlight.return_value.wait_for_connection.assert_called_once()
    aperture_scatterguard.return_value.wait_for_connection.assert_called_once()


@patch("artemis.experiment_plans.fast_grid_scan_plan.EigerDetector")
@patch("artemis.experiment_plans.fast_grid_scan_plan.FGSComposite")
@patch("artemis.experiment_plans.fast_grid_scan_plan.get_beamline_parameters")
def test_when_blueskyrunner_initiated_and_skip_flag_is_set_then_plans_are_setup_and_devices_are_not_connected(
    mock_get_beamline_params, mock_fgs, mock_eiger
):
    BlueskyRunner(MagicMock(), skip_startup_connection=True)
    mock_fgs.return_value.wait_for_connection.assert_not_called()


@patch("artemis.experiment_plans.fast_grid_scan_plan.EigerDetector")
@patch("artemis.experiment_plans.fast_grid_scan_plan.FGSComposite")
@patch("artemis.experiment_plans.fast_grid_scan_plan.get_beamline_parameters")
@patch("artemis.experiment_plans.fast_grid_scan_plan.create_devices")
def test_when_blueskyrunner_initiated_and_skip_flag_is_set_then_setup_called_upon_start(
    mock_setup, mock_get_beamline_params, mock_fgs, mock_eiger
):
    mock_setup = MagicMock()
    with patch.dict(
        "artemis.__main__.PLAN_REGISTRY",
        {
            "fast_grid_scan": {
                "setup": mock_setup,
                "run": MagicMock(),
                "param_type": MagicMock(),
                "callback_collection_type": MagicMock(),
            },
        },
    ):
        runner = BlueskyRunner(MagicMock(), skip_startup_connection=True)
        mock_setup.assert_not_called()
        runner.start(MagicMock(), MagicMock(), "fast_grid_scan")
        mock_setup.assert_called_once()


@pytest.mark.skip(reason="fixed in #595")
@patch("artemis.experiment_plans.fast_grid_scan_plan.EigerDetector")
@patch("artemis.experiment_plans.fast_grid_scan_plan.FGSComposite")
@patch("artemis.experiment_plans.fast_grid_scan_plan.get_beamline_parameters")
def test_when_blueskyrunner_initiated_and_skip_flag_is_not_set_then_all_plans_setup(
    mock_get_beamline_params,
    mock_fgs,
    mock_eiger,
):
    mock_setup = MagicMock()
    with patch.dict(
        "artemis.__main__.PLAN_REGISTRY",
        {
            "fast_grid_scan": {
                "setup": mock_setup,
                "run": MagicMock(),
                "param_type": MagicMock(),
                "callback_collection_type": MagicMock(),
            },
            "other_plan": {
                "setup": mock_setup,
                "run": MagicMock(),
                "param_type": MagicMock(),
                "callback_collection_type": MagicMock(),
            },
            "yet_another_plan": {
                "setup": mock_setup,
                "run": MagicMock(),
                "param_type": MagicMock(),
                "callback_collection_type": MagicMock(),
            },
        },
    ):
        BlueskyRunner(MagicMock(), skip_startup_connection=False)
        assert mock_setup.call_count == 3
