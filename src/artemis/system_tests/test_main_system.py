import pytest

from flask.testing import FlaskClient

from src.artemis.main import create_app
import json
from time import sleep

FGS_ENDPOINT = "/fast_grid_scan/"
START_ENDPOINT = FGS_ENDPOINT + "start"
STOP_ENDPOINT = FGS_ENDPOINT + "stop"
STATUS_ENDPOINT = FGS_ENDPOINT + "status"
TEST_PARAMS = {"grid": "scan"}


@pytest.fixture
def client():
    app, runner = create_app({"TESTING": True})

    with app.test_client() as client:
        yield client

    runner.stop()


def check_status_in_response(response_object, expected_result):
    response_json = json.loads(response_object.data)
    assert response_json["status"] == expected_result


def test_start_gives_success(client: FlaskClient):
    rv = client.put(START_ENDPOINT, data=json.dumps(TEST_PARAMS))
    check_status_in_response(rv, "Success")


def test_getting_status_return_idle(client: FlaskClient):
    rv = client.get(STATUS_ENDPOINT)
    check_status_in_response(rv, "Idle")


def test_getting_status_after_start_sent_returns_busy(client: FlaskClient):
    client.put(START_ENDPOINT, data=json.dumps(TEST_PARAMS))
    rv = client.get(STATUS_ENDPOINT)
    check_status_in_response(rv, "Busy")


def test_sending_start_twice_fails(client: FlaskClient):
    client.put(START_ENDPOINT, data=json.dumps(TEST_PARAMS))
    rv = client.put(START_ENDPOINT, data=json.dumps(TEST_PARAMS))
    check_status_in_response(rv, "Failed")


def test_given_started_when_stopped_then_success_and_ilde_status(client: FlaskClient):
    client.put(START_ENDPOINT, data=json.dumps(TEST_PARAMS))
    rv = client.put(STOP_ENDPOINT)
    check_status_in_response(rv, "Success")
    rv = client.get(STATUS_ENDPOINT)
    check_status_in_response(rv, "Idle")
