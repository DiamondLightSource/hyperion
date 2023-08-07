from __future__ import annotations

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
from artemis.exceptions import WarningException
from artemis.experiment_plans.experiment_registry import PLAN_REGISTRY
from artemis.parameters import external_parameters
from artemis.parameters.plan_specific.fgs_internal_params import FGSInternalParameters

FGS_ENDPOINT = "/fast_grid_scan/"
START_ENDPOINT = FGS_ENDPOINT + Actions.START.value
STOP_ENDPOINT = Actions.STOP.value
STATUS_ENDPOINT = Actions.STATUS.value
SHUTDOWN_ENDPOINT = Actions.SHUTDOWN.value
TEST_BAD_PARAM_ENDPOINT = "/fgs_real_params/" + Actions.START.value
TEST_PARAMS = json.dumps(external_parameters.from_file("test_parameter_defaults.json"))

SECS_PER_RUNENGINE_LOOP = 0.1
RUNENGINE_TAKES_TIME_TIMEOUT = 15

"""
Every test in this file which uses the test_env fixture should either:
    - set RE_takes_time to false
    or
    - set an error on the mock run engine
In order to avoid threads which get left alive forever after test completion
"""


class MockRunEngine:
    RE_takes_time = True
    aborting_takes_time = False
    error: Optional[Exception] = None

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        time = 0.0
        while self.RE_takes_time:
            sleep(SECS_PER_RUNENGINE_LOOP)
            time += SECS_PER_RUNENGINE_LOOP
            if self.error:
                raise self.error
            if time > RUNENGINE_TAKES_TIME_TIMEOUT:
                raise TimeoutError(
                    "Mock RunEngine thread spun too long without an error. Most likely "
                    "you should initialise with RE_takes_time=false, or set RE.error "
                    "from another thread."
                )

    def abort(self):
        while self.aborting_takes_time:
            sleep(SECS_PER_RUNENGINE_LOOP)
            if self.error:
                raise self.error
        self.RE_takes_time = False

    def subscribe(self, *args):
        pass


@dataclass
class ClientAndRunEngine:
    client: FlaskClient
    mock_run_engine: MockRunEngine


def mock_dict_values(d: dict):
    return {k: MagicMock() if k == "setup" or k == "run" else v for k, v in d.items()}


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
    "fgs_real_params": {
        "setup": MagicMock(),
        "run": MagicMock(),
        "internal_param_type": FGSInternalParameters,
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
    runner_thread.join(timeout=3)


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
    test_env.client.put(START_ENDPOINT, data=TEST_PARAMS)
    test_env.client.put(STOP_ENDPOINT)
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
        == "PlanNotFound(\"Corresponding internal param type for 'test_experiment_no_internal_param_type' not found in registry.\")"
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
    caplog,
    test_env: ClientAndRunEngine,
):
    test_env.mock_run_engine.aborting_takes_time = True

    test_env.client.put(START_ENDPOINT, data=TEST_PARAMS)
    test_env.mock_run_engine.error = Exception("D'Oh")
    response_json = wait_for_run_engine_status(test_env.client)
    assert response_json["status"] == Status.FAILED.value
    assert response_json["message"] == 'Exception("D\'Oh")'
    assert response_json["exception_type"] == "Exception"
    assert caplog.records[-1].levelname == "ERROR"


def test_when_started_n_returnstatus_interrupted_bc_RE_aborted_thn_error_reptd(
    test_env: ClientAndRunEngine,
):
    test_env.mock_run_engine.aborting_takes_time = True
    test_env.client.put(START_ENDPOINT, data=TEST_PARAMS)
    test_env.client.put(STOP_ENDPOINT)
    test_env.mock_run_engine.error = Exception("D'Oh")
    response_json = wait_for_run_engine_status(
        test_env.client, lambda status: status != Status.ABORTING.value
    )
    assert response_json["status"] == Status.FAILED.value
    assert response_json["message"] == 'Exception("D\'Oh")'
    assert response_json["exception_type"] == "Exception"


def test_given_started_when_RE_stops_on_its_own_happily_then_no_error_reported(
    test_env: ClientAndRunEngine,
):
    test_env.client.put(START_ENDPOINT, data=TEST_PARAMS)
    test_env.mock_run_engine.RE_takes_time = False
    response_json = wait_for_run_engine_status(test_env.client)
    assert response_json["status"] == Status.IDLE.value


def test_start_with_json_file_gives_success(test_env: ClientAndRunEngine):
    test_env.mock_run_engine.RE_takes_time = False

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
        "--skip-startup-connection",
    ]
    test_args = cli_arg_parse()
    assert test_args == ("DEBUG", True, True, True)


@patch("dodal.beamlines.i03.Attenuator", autospec=True, spec_set=True)
@patch("dodal.beamlines.i03.Flux", autospec=True, spec_set=True)
@patch("dodal.beamlines.i03.DetectorMotion", autospec=True, spec_set=True)
@patch("dodal.beamlines.i03.OAV", autospec=True, spec_set=True)
@patch("dodal.beamlines.i03.ApertureScatterguard", autospec=True, spec_set=True)
@patch("dodal.beamlines.i03.Backlight", autospec=True, spec_set=True)
@patch("dodal.beamlines.i03.EigerDetector", autospec=True, spec_set=True)
@patch("dodal.beamlines.i03.FastGridScan", autospec=True, spec_set=True)
@patch("dodal.beamlines.i03.S4SlitGaps", autospec=True, spec_set=True)
@patch("dodal.beamlines.i03.Smargon", autospec=True, spec_set=True)
@patch("dodal.beamlines.i03.Synchrotron", autospec=True, spec_set=True)
@patch("dodal.beamlines.i03.Undulator", autospec=True, spec_set=True)
@patch("dodal.beamlines.i03.Zebra", autospec=True, spec_set=True)
@patch(
    "artemis.experiment_plans.fast_grid_scan_plan.get_beamline_parameters",
    autospec=True,
)
@patch("dodal.beamlines.beamline_utils.active_device_is_same_type", autospec=True)
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
    oav,
    detector_motion,
    attenuator,
    flux,
):
    type_comparison.return_value = True
    BlueskyRunner(MagicMock(), skip_startup_connection=False)
    zebra.return_value.wait_for_connection.assert_called()
    undulator.return_value.wait_for_connection.assert_called()
    synchrotron.return_value.wait_for_connection.assert_called()
    smargon.return_value.wait_for_connection.assert_called()
    s4_slits.return_value.wait_for_connection.assert_called()
    fast_grid_scan.return_value.wait_for_connection.assert_called()
    eiger.return_value.wait_for_connection.assert_called()
    backlight.return_value.wait_for_connection.assert_called()
    aperture_scatterguard.return_value.wait_for_connection.assert_called()
    oav.return_value.wait_for_connection.assert_called()
    detector_motion.return_value.wait_for_connection.assert_called()
    attenuator.return_value.wait_for_connection.assert_called()
    flux.return_value.wait_for_connection.assert_called()


@patch(
    "artemis.experiment_plans.fast_grid_scan_plan.EigerDetector",
    autospec=True,
    spec_set=True,
)
@patch(
    "artemis.experiment_plans.fast_grid_scan_plan.FGSComposite",
    autospec=True,
    spec_set=True,
)
@patch(
    "artemis.experiment_plans.fast_grid_scan_plan.get_beamline_parameters",
    autospec=True,
)
@patch("artemis.experiment_plans.fast_grid_scan_plan.create_devices", autospec=True)
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
        runner.start(None, None, "fast_grid_scan")
        mock_setup.assert_called_once()


@patch(
    "artemis.experiment_plans.fast_grid_scan_plan.EigerDetector",
    autospec=True,
    spec_set=True,
)
@patch(
    "artemis.experiment_plans.fast_grid_scan_plan.FGSComposite",
    autospec=True,
    spec_set=True,
)
@patch(
    "artemis.experiment_plans.fast_grid_scan_plan.get_beamline_parameters",
    autospec=True,
)
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
            "rotation_scan": {
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
        clear=True,
    ):
        BlueskyRunner(MagicMock(), skip_startup_connection=False)
        assert mock_setup.call_count == 4


def test_log_on_invalid_json_params(test_env: ClientAndRunEngine):
    test_env.mock_run_engine.RE_takes_time = False
    response = test_env.client.put(TEST_BAD_PARAM_ENDPOINT, data='{"bad":1}').json
    assert isinstance(response, dict)
    assert response.get("status") == Status.FAILED.value
    assert (
        response.get("message")
        == "<ValidationError: \"{'bad': 1} does not have enough properties\">"
    )
    assert response.get("exception_type") == "ValidationError"


@pytest.mark.skip(
    reason="See https://github.com/DiamondLightSource/python-artemis/issues/777"
)
def test_warn_exception_during_plan_causes_warning_in_log(
    caplog, test_env: ClientAndRunEngine
):
    test_env.client.put(START_ENDPOINT, data=TEST_PARAMS)
    test_env.mock_run_engine.error = WarningException("D'Oh")
    response_json = wait_for_run_engine_status(test_env.client)
    assert response_json["status"] == Status.FAILED.value
    assert response_json["message"] == 'WarningException("D\'Oh")'
    assert response_json["exception_type"] == "WarningException"
    assert caplog.records[-1].levelname == "WARNING"
