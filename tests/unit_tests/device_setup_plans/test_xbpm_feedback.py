from unittest.mock import MagicMock

import pytest
from bluesky import plan_stubs as bps
from bluesky.run_engine import RunEngine
from bluesky.utils import FailedStatus
from dodal.devices.xbpm_feedback import Pause
from ophyd.status import Status
from ophyd_async.core import set_mock_value

from hyperion.device_setup_plans.xbpm_feedback import (
    transmission_and_xbpm_feedback_for_collection_decorator,
)


async def test_given_xpbm_checks_pass_when_plan_run_with_decorator_then_run_as_expected(
    RE,
    xbpm_feedback,
    attenuator,
):
    expected_transmission = 0.3

    @transmission_and_xbpm_feedback_for_collection_decorator(
        xbpm_feedback, attenuator, expected_transmission
    )
    def my_collection_plan():
        read_transmission = yield from bps.rd(attenuator.actual_transmission)
        assert read_transmission == expected_transmission
        pause_feedback = yield from bps.rd(xbpm_feedback.pause_feedback)
        assert pause_feedback == Pause.PAUSE

    set_mock_value(xbpm_feedback.pos_stable, True)  # type: ignore

    RE = RunEngine()
    RE(my_collection_plan())

    assert await attenuator.actual_transmission.get_value() == 1.0
    assert await xbpm_feedback.pause_feedback.get_value() == Pause.RUN


async def test_given_xbpm_checks_fail_when_plan_run_with_decorator_then_plan_not_run(
    RE,
    xbpm_feedback,
    attenuator,
):
    mock = MagicMock()

    @transmission_and_xbpm_feedback_for_collection_decorator(
        xbpm_feedback, attenuator, 0.1
    )
    def my_collection_plan():
        mock()
        yield from bps.null()

    xbpm_feedback.trigger = MagicMock(
        side_effect=lambda: Status(done=True, success=False)
    )

    RE = RunEngine()
    with pytest.raises(FailedStatus):
        RE(my_collection_plan())

    mock.assert_not_called()
    assert await attenuator.actual_transmission.get_value() == 1.0
    assert await xbpm_feedback.pause_feedback.get_value() == Pause.RUN


async def test_given_xpbm_checks_pass_and_plan_fails_when_plan_run_with_decorator_then_cleaned_up(
    RE,
    xbpm_feedback,
    attenuator,
):
    set_mock_value(xbpm_feedback.pos_stable, True)  # type: ignore

    class MyException(Exception):
        pass

    @transmission_and_xbpm_feedback_for_collection_decorator(
        xbpm_feedback, attenuator, 0.1
    )
    def my_collection_plan():
        yield from bps.null()
        raise MyException()

    RE = RunEngine()
    with pytest.raises(MyException):
        RE(my_collection_plan())

    assert await attenuator.actual_transmission.get_value() == 1.0
    assert await xbpm_feedback.pause_feedback.get_value() == Pause.RUN
