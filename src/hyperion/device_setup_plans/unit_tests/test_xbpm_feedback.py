from unittest.mock import MagicMock

import pytest
from bluesky import plan_stubs as bps
from bluesky.run_engine import RunEngine
from bluesky.utils import FailedStatus
from dodal.devices.attenuator import Attenuator
from dodal.devices.xbpm_feedback import XBPMFeedback
from ophyd.sim import make_fake_device
from ophyd.status import Status

from hyperion.device_setup_plans.xbpm_feedback import (
    transmission_and_xbpm_feedback_for_collection_decorator,
)


@pytest.fixture
def fake_devices():
    xbpm_feedback: XBPMFeedback = make_fake_device(XBPMFeedback)(name="xbpm")
    attenuator: Attenuator = make_fake_device(Attenuator)(name="atten")

    def fake_attenuator_set(val):
        attenuator.actual_transmission.sim_put(val)
        return Status(done=True, success=True)

    attenuator.set = MagicMock(side_effect=fake_attenuator_set)

    return xbpm_feedback, attenuator


def test_given_xpbm_checks_pass_when_plan_run_with_decorator_then_run_as_expected(
    fake_devices,
):
    xbpm_feedback: XBPMFeedback = fake_devices[0]
    attenuator: Attenuator = fake_devices[1]
    expected_transmission = 0.3

    @transmission_and_xbpm_feedback_for_collection_decorator(
        *fake_devices, expected_transmission
    )
    def my_collection_plan():
        assert attenuator.actual_transmission.get() == expected_transmission
        assert xbpm_feedback.pause_feedback.get() == 1
        yield from bps.null()

    xbpm_feedback.pos_stable.sim_put(1)

    RE = RunEngine()
    RE(my_collection_plan())

    assert attenuator.actual_transmission.get() == 1.0
    assert xbpm_feedback.pause_feedback.get() == 0


def test_given_xbpm_checks_fail_when_plan_run_with_decorator_then_plan_not_run(
    fake_devices,
):
    xbpm_feedback: XBPMFeedback = fake_devices[0]
    attenuator: Attenuator = fake_devices[1]
    mock = MagicMock()

    @transmission_and_xbpm_feedback_for_collection_decorator(*fake_devices, 0.1)
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
    assert xbpm_feedback.pause_feedback.get() == 0


def test_given_xpbm_checks_pass_and_plan_fails_when_plan_run_with_decorator_then_cleaned_up(
    fake_devices,
):
    xbpm_feedback: XBPMFeedback = fake_devices[0]
    attenuator: Attenuator = fake_devices[1]

    xbpm_feedback.pos_stable.sim_put(1)

    class MyException(Exception):
        pass

    @transmission_and_xbpm_feedback_for_collection_decorator(*fake_devices, 0.1)
    def my_collection_plan():
        yield from bps.null()
        raise MyException()

    RE = RunEngine()
    with pytest.raises(MyException):
        RE(my_collection_plan())

    assert attenuator.actual_transmission.get() == 1.0
    assert xbpm_feedback.pause_feedback.get() == 0
