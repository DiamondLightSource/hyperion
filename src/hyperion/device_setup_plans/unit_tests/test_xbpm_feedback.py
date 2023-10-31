from asyncio import wait_for
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from bluesky import RunEngine
from bluesky import plan_stubs as bps
from bluesky.run_engine import RunEngine
from bluesky.utils import FailedStatus
from dodal.devices.attenuator import Attenuator
from dodal.devices.xbpm_feedback import XBPMFeedbackI03
from ophyd.sim import make_fake_device
from ophyd.status import Status
from ophyd_async.core import DeviceCollector, set_sim_value

from hyperion.device_setup_plans.xbpm_feedback import (
    transmission_and_xbpm_feedback_for_collection_decorator,
)

# NEED TO DO TESTS USING OPHYD V2 SIM - EG OPHYD_ASYNC.CORE.SET_SIM_VALUE
# ALSO ADD TEST FOR THE NEW SUBCLASS OF XBPM

pytest_plugins = ("pytest_asyncio",)


@pytest_asyncio.fixture
async def fake_xbpm_feedback_i03():
    async with DeviceCollector(sim=True):
        xbpm_feedback = XBPMFeedbackI03(prefix="", name="xbpm")

    def fake_xbpm_feedback_set(val):
        set_sim_value(xbpm_feedback.pause_feedback, val)
        return Status(done=True, success=True)

    xbpm_feedback.pause_feedback.set = MagicMock(side_effect=fake_xbpm_feedback_set)

    yield xbpm_feedback


@pytest.fixture
def fake_attenuator():
    attenuator: Attenuator = make_fake_device(Attenuator)(name="atten")

    def fake_attenuator_set(val):
        attenuator.actual_transmission.sim_put(val)
        return Status(done=True, success=True)

    attenuator.set = MagicMock(side_effect=fake_attenuator_set)
    return attenuator


@pytest.mark.asyncio
async def test_given_xpbm_checks_pass_when_plan_run_with_decorator_then_run_as_expected(
    fake_xbpm_feedback_i03: XBPMFeedbackI03, fake_attenuator: Attenuator
):
    expected_transmission = 0.3

    @transmission_and_xbpm_feedback_for_collection_decorator(
        fake_xbpm_feedback_i03, fake_attenuator, expected_transmission
    )
    async def my_collection_plan():
        assert fake_attenuator.actual_transmission.get() == expected_transmission
        assert (
            await fake_xbpm_feedback_i03.pause_feedback.get_value()
            == fake_xbpm_feedback_i03.PAUSE
        )
        yield bps.null()

    set_sim_value(fake_xbpm_feedback_i03.pos_stable, 1)

    RE = RunEngine()
    RE(my_collection_plan())

    assert fake_attenuator.actual_transmission.get() == 1.0
    assert (
        fake_xbpm_feedback_i03.pause_feedback.get_value() == fake_xbpm_feedback_i03.RUN
    )


@pytest.mark.asyncio
def test_given_xbpm_checks_fail_when_plan_run_with_decorator_then_plan_not_run(
    fake_devices,
):
    xbpm_feedback: XBPMFeedbackI03 = fake_devices[0]
    attenuator: Attenuator = fake_devices[1]
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
    assert attenuator.actual_transmission.get() == 1.0
    assert xbpm_feedback.pause_feedback.get() == xbpm_feedback.RUN


def test_given_xpbm_checks_pass_and_plan_fails_when_plan_run_with_decorator_then_cleaned_up(
    fake_devices,
):
    xbpm_feedback: XBPMFeedbackI03 = fake_devices[0]
    attenuator: Attenuator = fake_devices[1]

    xbpm_feedback.pos_ok.sim_put(1)

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

    assert attenuator.actual_transmission.get() == 1.0
    assert xbpm_feedback.pause_feedback.get() == xbpm_feedback.RUN
