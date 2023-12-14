from unittest.mock import MagicMock, patch

import pytest
from ispyb.sp.mxacquisition import MXAcquisition

from hyperion.external_interaction.ispyb.store_robot_action_in_ispyb import (
    StoreRobotLoadInIspyb,
)
from hyperion.parameters.external_parameters import from_file as raw_params_from_file
from hyperion.parameters.plan_specific.wait_for_robot_load_then_center_params import (
    WaitForRobotLoadThenCentreInternalParameters,
)

TEST_SESSION_ID = 76523
TEST_ROBOT_ACTION_ENTRY_ID = 432423


@pytest.fixture
def wait_for_robot_load_then_centre_params():
    params = raw_params_from_file(
        "tests/test_data/parameter_json_files/good_test_wait_for_robot_load_params.json"
    )
    return WaitForRobotLoadThenCentreInternalParameters(**params)


def setup_mock_return_values(ispyb_conn):
    mx_acquisition = MXAcquisition()
    conn: MagicMock = ispyb_conn.return_value.__enter__.return_value
    conn.mx_acquisition = mx_acquisition
    conn.core.retrieve_visit_id.return_value = TEST_SESSION_ID

    mx_acquisition.upsert_robot_action = MagicMock(
        return_value=TEST_ROBOT_ACTION_ENTRY_ID
    )
    return mx_acquisition.upsert_robot_action


def get_nicely_formatted_upsert_args(upsert_func):
    upsert_args = upsert_func.call_args[0][0]

    robot_params_keys = MXAcquisition.get_robot_action_params().keys()
    return dict(zip(robot_params_keys, upsert_args))


@patch("ispyb.open", autospec=True)
def test_given_correct_ispyb_params_when_begin_deposition_then_data_upserted(
    ispyb_conn,
    wait_for_robot_load_then_centre_params,
):
    upsert_func = setup_mock_return_values(ispyb_conn)
    robot_load_in_ispyb = StoreRobotLoadInIspyb(
        "", wait_for_robot_load_then_centre_params
    )
    robot_load_in_ispyb.begin_deposition()
    data_deposited = get_nicely_formatted_upsert_args(upsert_func)

    assert data_deposited["sessionid"] == TEST_SESSION_ID
    assert data_deposited["actiontype"] == "LOAD"
    assert data_deposited["containerlocation"] == 10
    assert data_deposited["dewarlocation"] == 7
    assert data_deposited["starttimestamp"] is not None
    assert data_deposited["endtimestamp"] is None
    assert data_deposited["status"] is None
    assert data_deposited["message"] is None

    assert robot_load_in_ispyb.entry_id == TEST_ROBOT_ACTION_ENTRY_ID


@patch("ispyb.open", autospec=True)
def test_given_correct_ispyb_params_when_end_deposition_then_data_upserted(
    ispyb_conn,
    wait_for_robot_load_then_centre_params,
):
    upsert_func = setup_mock_return_values(ispyb_conn)
    robot_load_in_ispyb = StoreRobotLoadInIspyb(
        "", wait_for_robot_load_then_centre_params
    )
    robot_load_in_ispyb.entry_id = TEST_ROBOT_ACTION_ENTRY_ID
    test_success = "ERROR"
    test_reason = "Bad"
    robot_load_in_ispyb.end_deposition(test_success, test_reason)

    data_deposited = get_nicely_formatted_upsert_args(upsert_func)

    assert data_deposited["id"] == TEST_ROBOT_ACTION_ENTRY_ID
    assert data_deposited["sessionid"] == TEST_SESSION_ID
    assert data_deposited["actiontype"] is None
    assert data_deposited["endtimestamp"] is not None
    assert data_deposited["status"] == test_success
    assert data_deposited["message"] == test_reason
    assert data_deposited["snapshotafter"] is not None
    assert data_deposited["snapshotbefore"] is not None
