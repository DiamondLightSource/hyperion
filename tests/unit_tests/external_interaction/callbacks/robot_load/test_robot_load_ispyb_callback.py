from unittest.mock import MagicMock, patch

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import pytest
from bluesky.run_engine import RunEngine

from hyperion.external_interaction.callbacks.robot_load.ispyb_callback import (
    RobotLoadISPyBCallback,
)
from hyperion.parameters.constants import CONST

SAMPLE_ID = 231412
SAMPLE_PUCK = 50
SAMPLE_PIN = 4

metadata = {
    "subplan_name": CONST.PLAN.ROBOT_LOAD,
    "metadata": {
        "sample_id": SAMPLE_ID,
        "sample_puck": SAMPLE_PUCK,
        "sample_pin": SAMPLE_PIN,
    },
    "activate_callbacks": [
        "RobotLoadISPyBCallback",
    ],
}


@patch("hyperion.external_interaction.callbacks.robot_load.ispyb_callback.end_load")
@patch("hyperion.external_interaction.callbacks.robot_load.ispyb_callback.start_load")
def test_given_start_doc_with_expected_data_then_data_put_in_ispyb(
    start_load: MagicMock,
    end_load: MagicMock,
):
    @bpp.run_decorator(md=metadata)
    def my_plan():
        yield from bps.null()

    RE = RunEngine()
    RE.subscribe(RobotLoadISPyBCallback())

    RE(my_plan())

    start_load.assert_called_once_with(SAMPLE_ID, SAMPLE_PUCK, SAMPLE_PIN)
    end_load.assert_called_once_with("success", "")


@patch("hyperion.external_interaction.callbacks.robot_load.ispyb_callback.end_load")
@patch("hyperion.external_interaction.callbacks.robot_load.ispyb_callback.start_load")
def test_given_failing_plan_then_exception_detail(
    start_load: MagicMock,
    end_load: MagicMock,
):
    @bpp.run_decorator(md=metadata)
    def my_plan():
        raise Exception("BAD")
        yield from bps.null()

    RE = RunEngine()
    RE.subscribe(RobotLoadISPyBCallback())

    with pytest.raises(Exception):
        RE(my_plan())

    start_load.assert_called_once_with(SAMPLE_ID, SAMPLE_PUCK, SAMPLE_PIN)
    end_load.assert_called_once_with("fail", "BAD")
