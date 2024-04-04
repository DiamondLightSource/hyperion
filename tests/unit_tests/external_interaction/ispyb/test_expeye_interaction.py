from unittest.mock import ANY, patch

import pytest

from hyperion.external_interaction.exceptions import ISPyBDepositionNotMade
from hyperion.external_interaction.ispyb.exp_eye_store import (
    BearerAuth,
    ExpeyeInteraction,
    _get_base_url_and_token,
)


def test_get_url_and_token_returns_expected_data():
    url, token = _get_base_url_and_token()
    assert url == "http://blah"
    assert token == "notatoken"


@patch("hyperion.external_interaction.ispyb.exp_eye_store.post")
def test_when_start_load_called_then_correct_expected_url_posted_to_with_expected_data(
    mock_post,
):
    expeye_interactor = ExpeyeInteraction()
    expeye_interactor.start_load("test", 3, 700, 10, 5)

    mock_post.assert_called_once()
    assert (
        mock_post.call_args.args[0]
        == "http://blah/core/proposals/test/sessions/3/robot-actions"
    )
    expected_data = {
        "startTimestamp": ANY,
        "sampleId": 700,
        "actionType": "LOAD",
        "containerLocation": 5,
        "dewarLocation": 10,
    }
    assert mock_post.call_args.kwargs["json"] == expected_data


@patch("hyperion.external_interaction.ispyb.exp_eye_store.post")
def test_when_start_called_then_returns_id(mock_post):
    mock_post.return_value.json.return_value = {"robotActionId": 190}
    expeye_interactor = ExpeyeInteraction()
    robot_id = expeye_interactor.start_load("test", 3, 700, 10, 5)
    assert robot_id == 190


@patch("hyperion.external_interaction.ispyb.exp_eye_store.post")
def test_when_start_load_called_then_use_correct_token(
    mock_post,
):
    expeye_interactor = ExpeyeInteraction()
    expeye_interactor.start_load("test", 3, 700, 10, 5)

    assert isinstance(auth := mock_post.call_args.kwargs["auth"], BearerAuth)
    assert auth.token == "notatoken"


@patch("hyperion.external_interaction.ispyb.exp_eye_store.post")
def test_given_server_does_not_respond_when_start_load_called_then_error(mock_post):
    mock_post.return_value.ok = False

    expeye_interactor = ExpeyeInteraction()
    with pytest.raises(ISPyBDepositionNotMade):
        expeye_interactor.start_load("test", 3, 700, 10, 5)


@patch("hyperion.external_interaction.ispyb.exp_eye_store.patch")
def test_when_end_load_called_with_success_then_correct_expected_url_posted_to_with_expected_data(
    mock_patch,
):
    expeye_interactor = ExpeyeInteraction()
    expeye_interactor.end_load(3, "success", "")

    mock_patch.assert_called_once()
    assert mock_patch.call_args.args[0] == "http://blah/core/robot-actions/3"
    expected_data = {
        "endTimestamp": ANY,
        "status": "SUCCESS",
        "message": "",
    }
    assert mock_patch.call_args.kwargs["json"] == expected_data


@patch("hyperion.external_interaction.ispyb.exp_eye_store.patch")
def test_when_end_load_called_with_failure_then_correct_expected_url_posted_to_with_expected_data(
    mock_patch,
):
    expeye_interactor = ExpeyeInteraction()
    expeye_interactor.end_load(3, "fail", "bad")

    mock_patch.assert_called_once()
    assert mock_patch.call_args.args[0] == "http://blah/core/robot-actions/3"
    expected_data = {
        "endTimestamp": ANY,
        "status": "ERROR",
        "message": "bad",
    }
    assert mock_patch.call_args.kwargs["json"] == expected_data


@patch("hyperion.external_interaction.ispyb.exp_eye_store.patch")
def test_when_end_load_called_then_use_correct_token(
    mock_patch,
):
    expeye_interactor = ExpeyeInteraction()
    expeye_interactor.end_load(3, "success", "")

    assert isinstance(auth := mock_patch.call_args.kwargs["auth"], BearerAuth)
    assert auth.token == "notatoken"


@patch("hyperion.external_interaction.ispyb.exp_eye_store.patch")
def test_given_server_does_not_respond_when_end_load_called_then_error(mock_patch):
    mock_patch.return_value.ok = False

    expeye_interactor = ExpeyeInteraction()
    with pytest.raises(ISPyBDepositionNotMade):
        expeye_interactor.end_load(1, "", "")
