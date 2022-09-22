import json
import threading
from dataclasses import dataclass
from time import sleep
from typing import Any, Callable, NamedTuple, Optional
from unittest.mock import patch

import pytest
from flask.testing import FlaskClient

from artemis.__main__ import Actions, Status, create_app
from artemis.flux_parameters import FluxCalculationParameters, FluxPredictionParameters
from artemis.parameters import FullParameters


class TestSetup(NamedTuple):
    endpoint: str
    start_endpoint: str
    stop_endpoint: str
    status_endpoint: str
    shutdown_endpoint: str
    params: Any


FGS_ENDPOINT = "/fast_grid_scan/"
FGS_START_ENDPOINT = FGS_ENDPOINT + Actions.START.value
FGS_STOP_ENDPOINT = FGS_ENDPOINT + Actions.STOP.value
FGS_STATUS_ENDPOINT = FGS_ENDPOINT + "status"
FGS_SHUTDOWN_ENDPOINT = FGS_ENDPOINT + Actions.SHUTDOWN.value
FGS_TEST_PARAMS = FullParameters().to_json()


FGS_TEST_SETUP = TestSetup(
    FGS_ENDPOINT,
    FGS_START_ENDPOINT,
    FGS_STOP_ENDPOINT,
    FGS_STATUS_ENDPOINT,
    FGS_SHUTDOWN_ENDPOINT,
    FGS_TEST_PARAMS,
)


FLUX_CALC_ENDPOINT = "/flux_calculation/"
FLUX_CALC_START_ENDPOINT = FLUX_CALC_ENDPOINT + Actions.START.value
FLUX_CALC_STOP_ENDPOINT = FLUX_CALC_ENDPOINT + Actions.STOP.value
FLUX_CALC_STATUS_ENDPOINT = FLUX_CALC_ENDPOINT + "status"
FLUX_CALC_SHUTDOWN_ENDPOINT = FLUX_CALC_ENDPOINT + Actions.SHUTDOWN.value
FLUX_CALC_TEST_PARAMS = FluxCalculationParameters(beamline="BL03I").to_json()


FLUX_CALC_TEST_SETUP = TestSetup(
    FLUX_CALC_ENDPOINT,
    FLUX_CALC_START_ENDPOINT,
    FLUX_CALC_STOP_ENDPOINT,
    FLUX_CALC_STATUS_ENDPOINT,
    FLUX_CALC_SHUTDOWN_ENDPOINT,
    FLUX_CALC_TEST_PARAMS,
)

FLUX_PREDICTION_ENDPOINT = "/flux_prediction/"
FLUX_PREDICTION_START_ENDPOINT = FLUX_PREDICTION_ENDPOINT + Actions.START.value
FLUX_PREDICTION_STOP_ENDPOINT = FLUX_PREDICTION_ENDPOINT + Actions.STOP.value
FLUX_PREDICTION_STATUS_ENDPOINT = FLUX_PREDICTION_ENDPOINT + "status"
FLUX_PREDICTION_SHUTDOWN_ENDPOINT = FLUX_PREDICTION_ENDPOINT + Actions.SHUTDOWN.value
FLUX_PREDICTION_TEST_PARAMS = FluxPredictionParameters().to_json()


FLUX_PREDICTION_TEST_SETUP = TestSetup(
    FLUX_PREDICTION_ENDPOINT,
    FLUX_PREDICTION_START_ENDPOINT,
    FLUX_PREDICTION_STOP_ENDPOINT,
    FLUX_PREDICTION_STATUS_ENDPOINT,
    FLUX_PREDICTION_SHUTDOWN_ENDPOINT,
    FLUX_PREDICTION_TEST_PARAMS,
)


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


@pytest.fixture
def test_env():
    mock_run_engine = MockRunEngine()
    app, runner = create_app({"TESTING": True}, mock_run_engine)
    runner_thread = threading.Thread(target=runner.wait_on_queue)
    runner_thread.start()
    with app.test_client() as client:
        with patch("artemis.__main__.get_fgs_plan"), patch(
            "artemis.__main__.get_flux_calculation_plan"
        ), patch("artemis.__main__.predict_flux"), patch("artemis.__main__.get_flux"):
            yield ClientAndRunEngine(client, mock_run_engine)

    runner.shutdown()
    runner_thread.join()


def wait_for_run_engine_status(
    client: FlaskClient,
    status_endpoint,
    status_check: Callable[[str], bool] = lambda status: status != Status.BUSY.value,
    attempts=10,
):
    while attempts != 0:
        response = client.get(status_endpoint)
        print("Data:", response.data)
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


@pytest.mark.parametrize(
    "test_setup",
    [FGS_TEST_SETUP, FLUX_CALC_TEST_SETUP, FLUX_PREDICTION_TEST_SETUP],
)
def test_start_gives_success(test_env: ClientAndRunEngine, test_setup):
    response = test_env.client.put(test_setup.start_endpoint, data=test_setup.params)
    check_status_in_response(response, Status.SUCCESS)


@pytest.mark.parametrize(
    "test_setup",
    [FGS_TEST_SETUP, FLUX_CALC_TEST_SETUP],
)
def test_getting_status_return_idle(test_env: ClientAndRunEngine, test_setup):
    response = test_env.client.get(test_setup.status_endpoint)
    check_status_in_response(response, Status.IDLE)


@pytest.mark.parametrize(
    "test_setup",
    [FGS_TEST_SETUP, FLUX_CALC_TEST_SETUP, FLUX_PREDICTION_TEST_SETUP],
)
def test_getting_status_after_start_sent_returns_busy(
    test_env: ClientAndRunEngine, test_setup
):
    test_env.client.put(test_setup.start_endpoint, data=test_setup.params)
    response = test_env.client.get(test_setup.status_endpoint)
    check_status_in_response(response, Status.BUSY)


@pytest.mark.parametrize(
    "test_setup",
    [FGS_TEST_SETUP, FLUX_CALC_TEST_SETUP, FLUX_PREDICTION_TEST_SETUP],
)
def test_sending_start_twice_fails(test_env: ClientAndRunEngine, test_setup):
    test_env.client.put(test_setup.start_endpoint, data=test_setup.params)
    response = test_env.client.put(test_setup.start_endpoint, data=test_setup.params)
    check_status_in_response(response, Status.FAILED)


@pytest.mark.parametrize(
    "test_setup",
    [FGS_TEST_SETUP, FLUX_CALC_TEST_SETUP, FLUX_PREDICTION_TEST_SETUP],
)
def test_given_started_when_stopped_then_success_and_idle_status(
    test_env: ClientAndRunEngine, test_setup
):
    test_env.mock_run_engine.aborting_takes_time = True
    test_env.client.put(test_setup.start_endpoint, data=test_setup.params)
    response = test_env.client.put(test_setup.stop_endpoint)
    check_status_in_response(response, Status.ABORTING)
    response = test_env.client.get(test_setup.status_endpoint)
    check_status_in_response(response, Status.ABORTING)
    test_env.mock_run_engine.aborting_takes_time = False
    wait_for_run_engine_status(
        test_env.client,
        status_endpoint=test_setup.status_endpoint,
        status_check=lambda status: status != Status.ABORTING,
    )
    check_status_in_response(response, Status.ABORTING)


@pytest.mark.parametrize(
    "test_setup",
    [FGS_TEST_SETUP, FLUX_CALC_TEST_SETUP, FLUX_PREDICTION_TEST_SETUP],
)
def test_given_started_when_stopped_and_started_again_then_runs(
    test_env: ClientAndRunEngine, test_setup
):
    test_env.client.put(test_setup.start_endpoint, data=test_setup.params)
    test_env.client.put(test_setup.stop_endpoint)
    response = test_env.client.put(test_setup.start_endpoint, data=test_setup.params)
    check_status_in_response(response, Status.SUCCESS)
    response = test_env.client.get(test_setup.status_endpoint)
    check_status_in_response(response, Status.BUSY)


@pytest.mark.parametrize(
    "test_setup",
    [FGS_TEST_SETUP, FLUX_CALC_TEST_SETUP, FLUX_PREDICTION_TEST_SETUP],
)
def test_given_started_when_RE_stops_on_its_own_with_error_then_error_reported(
    test_env: ClientAndRunEngine, test_setup
):
    test_env.client.put(test_setup.start_endpoint, data=test_setup.params)
    error_message = "D'Oh"
    test_env.mock_run_engine.error = error_message
    response_json = wait_for_run_engine_status(
        test_env.client, status_endpoint=test_setup.status_endpoint
    )
    assert response_json["status"] == Status.FAILED.value
    assert response_json["message"] == error_message


@pytest.mark.parametrize(
    "test_setup",
    [FGS_TEST_SETUP, FLUX_CALC_TEST_SETUP, FLUX_PREDICTION_TEST_SETUP],
)
def test_given_started_and_return_status_interrupted_when_RE_aborted_then_error_reported(
    test_env: ClientAndRunEngine, test_setup
):
    test_env.mock_run_engine.aborting_takes_time = True
    test_env.client.put(test_setup.start_endpoint, data=test_setup.params)
    error_message = "D'Oh"
    test_env.client.put(test_setup.stop_endpoint)
    test_env.mock_run_engine.error = error_message
    response_json = wait_for_run_engine_status(
        test_env.client,
        status_endpoint=test_setup.status_endpoint,
        status_check=lambda status: status != Status.ABORTING.value,
    )
    assert response_json["status"] == Status.FAILED.value
    assert response_json["message"] == error_message


@pytest.mark.parametrize(
    "test_setup",
    [FGS_TEST_SETUP, FLUX_CALC_TEST_SETUP, FLUX_PREDICTION_TEST_SETUP],
)
def test_given_started_when_RE_stops_on_its_own_happily_then_no_error_reported(
    test_env: ClientAndRunEngine, test_setup: TestSetup
):
    test_env.client.put(test_setup.start_endpoint, data=test_setup.params)
    test_env.mock_run_engine.RE_takes_time = False
    response_json = wait_for_run_engine_status(
        test_env.client, status_endpoint=test_setup.status_endpoint
    )
    assert response_json["status"] == Status.IDLE.value


@pytest.mark.parametrize(
    "test_setup",
    [FGS_TEST_SETUP, FLUX_CALC_TEST_SETUP, FLUX_PREDICTION_TEST_SETUP],
)
def test_start_with_json_file_gives_success(test_env: ClientAndRunEngine, test_setup):
    with open("test_parameters.json") as test_parameters_file:
        test_parameters_json = test_parameters_file.read()
    response = test_env.client.put(test_setup.start_endpoint, data=test_parameters_json)
    check_status_in_response(response, Status.SUCCESS)


@pytest.mark.parametrize(
    "test_setup",
    [FGS_TEST_SETUP, FLUX_CALC_TEST_SETUP, FLUX_PREDICTION_TEST_SETUP],
)
def test_json_decode_failure_gives_failure_status(
    test_env: ClientAndRunEngine, test_setup
):
    response = test_env.client.put(
        test_setup.start_endpoint, data=test_setup.params + "junk"
    )
    check_status_in_response(response, Status.FAILED)
