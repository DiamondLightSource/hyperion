from unittest.mock import MagicMock, patch

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import pytest
from bluesky.run_engine import RunEngine
from dodal.devices.oav.oav_detector import OAV
from dodal.devices.robot import BartRobot
from dodal.devices.webcam import Webcam
from ophyd_async.core import set_sim_value

from hyperion.external_interaction.callbacks.robot_load.ispyb_callback import (
    RobotLoadISPyBCallback,
)
from hyperion.parameters.constants import CONST

VISIT_PATH = "/tmp/cm31105-4"

SAMPLE_ID = 231412
SAMPLE_PUCK = 50
SAMPLE_PIN = 4
ACTION_ID = 1098

metadata = {
    "subplan_name": CONST.PLAN.ROBOT_LOAD,
    "metadata": {
        "visit_path": VISIT_PATH,
        "sample_id": SAMPLE_ID,
        "sample_puck": SAMPLE_PUCK,
        "sample_pin": SAMPLE_PIN,
    },
    "activate_callbacks": [
        "RobotLoadISPyBCallback",
    ],
}


@patch(
    "hyperion.external_interaction.callbacks.robot_load.ispyb_callback.ExpeyeInteraction.end_load"
)
@patch(
    "hyperion.external_interaction.callbacks.robot_load.ispyb_callback.ExpeyeInteraction.start_load"
)
def test_given_start_doc_with_expected_data_then_data_put_in_ispyb(
    start_load: MagicMock,
    end_load: MagicMock,
):
    RE = RunEngine()
    RE.subscribe(RobotLoadISPyBCallback())
    start_load.return_value = ACTION_ID

    @bpp.run_decorator(md=metadata)
    def my_plan():
        yield from bps.null()

    RE(my_plan())

    start_load.assert_called_once_with("cm31105", 4, SAMPLE_ID, SAMPLE_PUCK, SAMPLE_PIN)
    end_load.assert_called_once_with(ACTION_ID, "success", "")


@patch(
    "hyperion.external_interaction.callbacks.robot_load.ispyb_callback.ExpeyeInteraction.end_load"
)
@patch(
    "hyperion.external_interaction.callbacks.robot_load.ispyb_callback.ExpeyeInteraction.start_load"
)
def test_given_failing_plan_then_exception_detail(
    start_load: MagicMock,
    end_load: MagicMock,
):
    RE = RunEngine()
    RE.subscribe(RobotLoadISPyBCallback())
    start_load.return_value = ACTION_ID

    @bpp.run_decorator(md=metadata)
    def my_plan():
        raise Exception("BAD")
        yield from bps.null()

    with pytest.raises(Exception):
        RE(my_plan())

    start_load.assert_called_once_with("cm31105", 4, SAMPLE_ID, SAMPLE_PUCK, SAMPLE_PIN)
    end_load.assert_called_once_with(ACTION_ID, "fail", "BAD")


@patch(
    "hyperion.external_interaction.callbacks.robot_load.ispyb_callback.ExpeyeInteraction.end_load"
)
def test_given_end_called_but_no_start_then_exception_raised(end_load):
    callback = RobotLoadISPyBCallback()
    callback.active = True
    with pytest.raises(AssertionError):
        callback.activity_gated_stop({"run_uid": None})  # type: ignore
    end_load.assert_not_called()


@patch(
    "hyperion.external_interaction.callbacks.robot_load.ispyb_callback.ExpeyeInteraction.end_load"
)
@patch(
    "hyperion.external_interaction.callbacks.robot_load.ispyb_callback.ExpeyeInteraction.start_load"
)
@patch(
    "hyperion.external_interaction.callbacks.robot_load.ispyb_callback.ExpeyeInteraction.update_barcode_and_snapshots"
)
def test_given_plan_reads_barcode_then_data_put_in_ispyb(
    update_barcode_and_snapshots: MagicMock,
    start_load: MagicMock,
    end_load: MagicMock,
    robot: BartRobot,
    oav: OAV,
    webcam: Webcam,
):
    RE = RunEngine()
    RE.subscribe(RobotLoadISPyBCallback())
    start_load.return_value = ACTION_ID

    oav.snapshot.last_saved_path.put("test_oav_snapshot")  # type: ignore
    set_sim_value(webcam.last_saved_path, "test_webcam_snapshot")

    @bpp.run_decorator(md=metadata)
    def my_plan():
        yield from bps.create(name=CONST.DESCRIPTORS.ROBOT_LOAD)
        yield from bps.read(robot.barcode)
        yield from bps.read(oav.snapshot)
        yield from bps.read(webcam)
        yield from bps.save()

    RE(my_plan())

    start_load.assert_called_once_with("cm31105", 4, SAMPLE_ID, SAMPLE_PUCK, SAMPLE_PIN)
    update_barcode_and_snapshots.assert_called_once_with(
        ACTION_ID, "BARCODE", "test_oav_snapshot", "test_webcam_snapshot"
    )
    end_load.assert_called_once_with(ACTION_ID, "success", "")
