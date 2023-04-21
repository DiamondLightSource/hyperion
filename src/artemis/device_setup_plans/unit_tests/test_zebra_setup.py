from unittest.mock import MagicMock, patch

import pytest
from bluesky.run_engine import RunEngine
from dodal import i03
from dodal.devices.zebra import (
    IN3_TTL,
    IN4_TTL,
    OR1,
    PC_PULSE,
    TTL_DETECTOR,
    TTL_SHUTTER,
    I03_axes,
    Zebra,
)
from ophyd.status import Status

from artemis.device_setup_plans.setup_zebra import (
    arm_zebra,
    disarm_zebra,
    set_zebra_shutter_to_manual,
    setup_zebra_for_fgs,
    setup_zebra_for_rotation,
)


@pytest.fixture
def RE():
    return RunEngine({})


@pytest.fixture
def zebra():
    return i03.zebra(fake_with_ophyd_sim=True)


@patch("bluesky.plan_stubs.wait")
def test_zebra_set_up_for_fgs(bps_wait, RE, zebra: Zebra):
    RE(setup_zebra_for_fgs(zebra, wait=True))
    assert zebra.output.out_pvs[TTL_DETECTOR].get() == IN3_TTL
    assert zebra.output.out_pvs[TTL_SHUTTER].get() == IN4_TTL


@patch("bluesky.plan_stubs.wait")
def test_zebra_set_up_for_rotation(bps_wait, RE, zebra: Zebra):
    RE(setup_zebra_for_rotation(zebra, wait=True))
    assert zebra.pc.gate_trigger.get(as_string=True) == I03_axes.OMEGA.value
    assert zebra.pc.gate_width.get() == pytest.approx(360, 0.01)


@patch("bluesky.plan_stubs.wait")
def test_zebra_cleanup(bps_wait, RE, zebra: Zebra):
    RE(set_zebra_shutter_to_manual(zebra, wait=True))
    assert zebra.output.out_pvs[TTL_DETECTOR].get() == PC_PULSE
    assert zebra.output.out_pvs[TTL_SHUTTER].get() == OR1


def test_zebra_arm_disarm(
    RE,
    zebra: Zebra,
):
    def side_effect(val: int):
        zebra.pc.armed.set(val)
        return Status(done=True, success=True)

    def fail_side_effect(val: int):
        zebra.pc.armed.set(0 if val else 1)
        return Status(done=False)

    mock_arm_disarm = MagicMock(side_effect=side_effect)
    mock_fail_arm_disarm = MagicMock(side_effect=fail_side_effect)

    zebra.pc.arm_demand.set = mock_arm_disarm

    zebra.pc.armed.set(0)
    RE(arm_zebra(zebra, 0.5))
    assert zebra.pc.is_armed()

    zebra.pc.armed.set(1)
    RE(disarm_zebra(zebra, 0.5))
    assert not zebra.pc.is_armed()

    zebra.pc.arm_demand.set = mock_fail_arm_disarm

    with pytest.raises(TimeoutError):
        zebra.pc.armed.set(0)
        RE(arm_zebra(zebra, 0.2))
    with pytest.raises(TimeoutError):
        zebra.pc.armed.set(1)
        RE(disarm_zebra(zebra, 0.2))
