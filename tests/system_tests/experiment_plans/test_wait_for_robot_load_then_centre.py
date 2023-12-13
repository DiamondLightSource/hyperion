import datetime
from contextlib import nullcontext
from unittest.mock import MagicMock, patch

import ispyb.sqlalchemy
import pytest
from bluesky.run_engine import RunEngine
from dodal.devices.smargon import Smargon
from ispyb.sqlalchemy import RobotAction
from ophyd.sim import instantiate_fake_device
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from hyperion.experiment_plans.wait_for_robot_load_then_centre import (
    wait_for_robot_load_then_centre,
)
from hyperion.external_interaction.ispyb.ispyb_utils import ISPYB_DATE_TIME_FORMAT
from hyperion.parameters.constants import DEV_ISPYB_DATABASE_CFG
from hyperion.parameters.external_parameters import from_file as raw_params_from_file
from hyperion.parameters.plan_specific.wait_for_robot_load_then_center_params import (
    WaitForRobotLoadThenCentreInternalParameters,
)


@pytest.fixture
def wait_for_robot_load_then_centre_params():
    params = raw_params_from_file(
        "tests/test_data/parameter_json_files/good_test_wait_for_robot_load_params.json"
    )
    return WaitForRobotLoadThenCentreInternalParameters(**params)


def run_plan_and_get_ispyb_data(
    mock_composite,
    wait_for_robot_load_then_centre_params,
    run_context_manager=nullcontext(),
) -> RobotAction:
    current_time = datetime.datetime.now().replace(microsecond=0)
    wait_for_robot_load_then_centre_params.experiment_params.robot_load_start_time = (
        current_time.strftime(ISPYB_DATE_TIME_FORMAT)
    )

    RE = RunEngine()
    with run_context_manager:
        RE(
            wait_for_robot_load_then_centre(
                mock_composite, wait_for_robot_load_then_centre_params
            )
        )

    url = ispyb.sqlalchemy.url(DEV_ISPYB_DATABASE_CFG)
    engine = create_engine(url, connect_args={"use_pure": True})

    with Session(bind=engine) as session:
        query = (
            session.query(RobotAction)
            .filter(RobotAction.blsampleId == 5054650)  # type: ignore
            .order_by(RobotAction.robotActionId.desc())
        )
        first_result: RobotAction = query.first()

    assert first_result
    assert first_result.dewarLocation == 7
    assert first_result.containerLocation == 10
    assert first_result.startTimestamp == current_time

    time_taken = first_result.endTimestamp - first_result.startTimestamp
    assert time_taken < datetime.timedelta(2)

    return first_result


@pytest.mark.s03
@patch(
    "hyperion.experiment_plans.wait_for_robot_load_then_centre.pin_tip_centre_then_xray_centre"
)
@patch(
    "hyperion.external_interaction.callbacks.robot_load.ispyb_callback.get_ispyb_config",
    MagicMock(return_value=DEV_ISPYB_DATABASE_CFG),
)
def test_given_using_dev_database_when_plan_runs_then_robot_load_ispyb_entry_made(
    mock_centring_plan: MagicMock,
    wait_for_robot_load_then_centre_params: WaitForRobotLoadThenCentreInternalParameters,
):
    mock_composite = MagicMock()
    mock_composite.smargon = instantiate_fake_device(Smargon, name="smargon")

    first_result = run_plan_and_get_ispyb_data(
        mock_composite, wait_for_robot_load_then_centre_params
    )

    assert first_result.status == "SUCCESS"
    assert first_result.message == "OK"


@pytest.mark.s03
@patch(
    "hyperion.experiment_plans.wait_for_robot_load_then_centre.pin_tip_centre_then_xray_centre"
)
@patch(
    "hyperion.external_interaction.callbacks.robot_load.ispyb_callback.get_ispyb_config",
    MagicMock(return_value=DEV_ISPYB_DATABASE_CFG),
)
def test_given_wait_for_robot_load_fails_and_using_dev_database_when_plan_runs_then_robot_load_ispyb_entry_made_with_failure(
    mock_centring_plan: MagicMock,
    wait_for_robot_load_then_centre_params: WaitForRobotLoadThenCentreInternalParameters,
):
    expected_exception = TimeoutError("Bad vibes")
    mock_composite = MagicMock()
    mock_composite.smargon = instantiate_fake_device(Smargon, name="smargon")
    mock_composite.smargon.disabled.read = MagicMock(side_effect=expected_exception)

    first_result = run_plan_and_get_ispyb_data(
        mock_composite,
        wait_for_robot_load_then_centre_params,
        pytest.raises(type(expected_exception)),  # type: ignore
    )

    assert first_result.status == "ERROR"
    assert first_result.message == str(expected_exception)
