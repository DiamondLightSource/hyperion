from dataclasses import dataclass
import pytest

from flask.testing import FlaskClient

from src.artemis.main import BlueskyRunner, create_app, Status, Actions
import json
from time import sleep
import collections

FGS_ENDPOINT = "/fast_grid_scan/"
START_ENDPOINT = FGS_ENDPOINT + Actions.START.value
STOP_ENDPOINT = FGS_ENDPOINT + Actions.STOP.value
STATUS_ENDPOINT = FGS_ENDPOINT + "status"
TEST_PARAMS = {"grid": "scan"}


@dataclass
class ClientAndRunner:
    client: FlaskClient
    runner: BlueskyRunner


@pytest.fixture
def test_env():
    app, runner = create_app({"TESTING": True})

    with app.test_client() as client:
        yield ClientAndRunner(client, runner)

    runner.stop()


def check_status_in_response(response_object, expected_result: Status):
    response_json = json.loads(response_object.data)
    assert response_json["status"] == expected_result.value


def test_start_gives_success(test_env: ClientAndRunner):
    response = test_env.client.put(START_ENDPOINT, data=json.dumps(TEST_PARAMS))
    check_status_in_response(response, Status.SUCCESS)


def test_getting_status_return_idle(test_env: ClientAndRunner):
    response = test_env.client.get(STATUS_ENDPOINT)
    check_status_in_response(response, Status.IDLE)


def test_getting_status_after_start_sent_returns_busy(
    test_env: ClientAndRunner,
):
    test_env.client.put(START_ENDPOINT, data=json.dumps(TEST_PARAMS))
    response = test_env.client.get(STATUS_ENDPOINT)
    check_status_in_response(response, Status.BUSY)


def test_sending_start_twice_fails(test_env: ClientAndRunner):
    test_env.client.put(START_ENDPOINT, data=json.dumps(TEST_PARAMS))
    response = test_env.client.put(START_ENDPOINT, data=json.dumps(TEST_PARAMS))
    check_status_in_response(response, Status.FAILED)


def test_given_started_when_stopped_then_success_and_ilde_status(
    test_env: ClientAndRunner,
):
    test_env.client.put(START_ENDPOINT, data=json.dumps(TEST_PARAMS))
    response = test_env.client.put(STOP_ENDPOINT)
    check_status_in_response(response, Status.SUCCESS)
    response = test_env.client.get(STATUS_ENDPOINT)
    check_status_in_response(response, Status.IDLE)


def test_given_started_when_stopped_and_started_again_then_runs(
    test_env: ClientAndRunner,
):
    test_env.client.put(START_ENDPOINT, data=json.dumps(TEST_PARAMS))
    test_env.client.put(STOP_ENDPOINT)
    response = test_env.client.put(START_ENDPOINT, data=json.dumps(TEST_PARAMS))
    check_status_in_response(response, Status.SUCCESS)
    response = test_env.client.get(START_ENDPOINT)
    check_status_in_response(response, Status.BUSY)


def test_given_started_when_error_occurs_then_failed_status_with_error_message(
    test_env: ClientAndRunner,
):
    test_error_message = "D'Oh"
    test_env.client.put(START_ENDPOINT, data=json.dumps(TEST_PARAMS))
    test_env.runner.set_error(test_error_message)
    response = test_env.client.get(STATUS_ENDPOINT)
    response_details = json.loads(response.data)
    assert response_details["status"] == Status.FAILED.value
    assert response_details["message"] == test_error_message
