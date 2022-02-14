from dataclasses import dataclass
import threading
import pytest
from typing import Any
from flask.testing import FlaskClient
from src.artemis.fast_grid_scan_plan import FullParameters

from src.artemis.main import create_app, Status, Actions
import json
from time import sleep
from bluesky.run_engine import RunEngineResult
from mockito import mock

FGS_ENDPOINT = "/fast_grid_scan/"
START_ENDPOINT = FGS_ENDPOINT + Actions.START.value
STOP_ENDPOINT = FGS_ENDPOINT + Actions.STOP.value
STATUS_ENDPOINT = FGS_ENDPOINT + "status"
SHUTDOWN_ENDPOINT = FGS_ENDPOINT + Actions.SHUTDOWN.value
TEST_PARAMS = FullParameters().to_json()


class MockRunEngine:
    RE_running = True
    return_status: RunEngineResult = mock()

    def __init__(self) -> None:
        self.return_status.interrupted = False

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        while self.RE_running:
            sleep(0.1)
        return self.return_status

    def abort(self):
        self.RE_running = False
        return self.return_status


@dataclass
class ClientAndRunEngine:
    client: FlaskClient
    mock_run_engine: MockRunEngine


@pytest.fixture
def test_env():
    app, runner = create_app({"TESTING": True})
    runner.RE = MockRunEngine()
    runner_thread = threading.Thread(target=runner.wait_on_queue)
    runner_thread.start()
    with app.test_client() as client:
        yield ClientAndRunEngine(client, runner.RE)
        client.get(SHUTDOWN_ENDPOINT)

    runner_thread.join()


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


def test_sending_start_twice_fails(test_env: ClientAndRunEngine):
    test_env.client.put(START_ENDPOINT, data=TEST_PARAMS)
    response = test_env.client.put(START_ENDPOINT, data=TEST_PARAMS)
    check_status_in_response(response, Status.FAILED)


def test_given_started_when_stopped_then_success_and_idle_status(
    test_env: ClientAndRunEngine,
):
    test_env.client.put(START_ENDPOINT, data=TEST_PARAMS)
    response = test_env.client.put(STOP_ENDPOINT)
    check_status_in_response(response, Status.SUCCESS)
    response = test_env.client.get(STATUS_ENDPOINT)
    check_status_in_response(response, Status.IDLE)


def test_given_started_when_stopped_and_started_again_then_runs(
    test_env: ClientAndRunEngine,
):
    test_env.client.put(START_ENDPOINT, data=TEST_PARAMS)
    test_env.client.put(STOP_ENDPOINT)
    response = test_env.client.put(START_ENDPOINT, data=TEST_PARAMS)
    check_status_in_response(response, Status.SUCCESS)
    response = test_env.client.get(STATUS_ENDPOINT)
    check_status_in_response(response, Status.BUSY)


def wait_for_not_busy(client: FlaskClient, attempts=10):
    while attempts != 0:
        response = client.get(STATUS_ENDPOINT)
        response_json = json.loads(response.data)
        if response_json["status"] != Status.BUSY.value:
            return response_json
        else:
            attempts -= 1
            sleep(0.1)
    assert False, "Run engine still busy"


def test_given_started_when_RE_stops_on_its_own_with_interrupt_then_error_reported(
    test_env: ClientAndRunEngine,
):
    test_env.client.put(START_ENDPOINT, data=TEST_PARAMS)
    error_message = "D'Oh"
    test_env.mock_run_engine.return_status.interrupted = True
    test_env.mock_run_engine.return_status.reason = error_message
    test_env.mock_run_engine.RE_running = False
    response_json = wait_for_not_busy(test_env.client)
    assert response_json["status"] == Status.FAILED.value
    assert response_json["message"] == error_message


def test_given_started_and_return_status_interrupted_when_RE_aborted_then_error_reported(
    test_env: ClientAndRunEngine,
):
    test_env.client.put(START_ENDPOINT, data=TEST_PARAMS)
    error_message = "D'Oh"
    test_env.mock_run_engine.return_status.interrupted = True
    test_env.mock_run_engine.return_status.reason = error_message
    test_env.client.put(STOP_ENDPOINT)
    response_json = wait_for_not_busy(test_env.client)
    assert response_json["status"] == Status.FAILED.value
    assert response_json["message"] == error_message


def test_given_started_when_RE_stops_on_its_own_happily_then_no_error_reported(
    test_env: ClientAndRunEngine,
):
    test_env.client.put(START_ENDPOINT, data=TEST_PARAMS)
    test_env.mock_run_engine.return_status.interrupted = False
    test_env.mock_run_engine.RE_running = False
    test_env.client.put(STOP_ENDPOINT)
    response_json = wait_for_not_busy(test_env.client)
    assert response_json["status"] == Status.IDLE.value
