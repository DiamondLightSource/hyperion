from functools import partial
from unittest.mock import MagicMock

import pytest
from bluesky.run_engine import RunEngine
from dodal.beamlines import i03
from dodal.devices.zebra import (
    IN3_TTL,
    IN4_TTL,
    OR1,
    PC_PULSE,
    TTL_DETECTOR,
    TTL_SHUTTER,
    I03Axes,
    Zebra,
)
from ophyd.status import Status

from hyperion.device_setup_plans.setup_zebra import (
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


def test_zebra_set_up_for_fgs(RE, zebra: Zebra):
    RE(setup_zebra_for_fgs(zebra, wait=True))
    assert zebra.output.out_pvs[TTL_DETECTOR].get() == IN3_TTL
    assert zebra.output.out_pvs[TTL_SHUTTER].get() == IN4_TTL


def test_zebra_set_up_for_rotation(RE, zebra: Zebra):
    RE(setup_zebra_for_rotation(zebra, wait=True))
    assert zebra.pc.gate_trigger.get(as_string=True) == I03Axes.OMEGA.value
    assert zebra.pc.gate_width.get() == pytest.approx(360, 0.01)
    with pytest.raises(ValueError):
        RE(setup_zebra_for_rotation(zebra, direction=25))


def test_zebra_cleanup(RE, zebra: Zebra):
    RE(set_zebra_shutter_to_manual(zebra, wait=True))
    assert zebra.output.out_pvs[TTL_DETECTOR].get() == PC_PULSE
    assert zebra.output.out_pvs[TTL_SHUTTER].get() == OR1


def test_zebra_arm_disarm(
    RE,
    zebra: Zebra,
):
    def side_effect(set_armed_to: int, _):
        zebra.pc.arm.armed.set(set_armed_to)
        return Status(done=True, success=True)

    zebra.pc.arm.TIMEOUT = 0.5

    mock_arm = MagicMock(side_effect=partial(side_effect, 1))
    mock_disarm = MagicMock(side_effect=partial(side_effect, 0))

    zebra.pc.arm.arm_set.set = mock_arm
    zebra.pc.arm.disarm_set.set = mock_disarm

    zebra.pc.arm.armed.set(0)
    RE(arm_zebra(zebra))
    assert zebra.pc.is_armed()

    zebra.pc.arm.armed.set(1)
    RE(disarm_zebra(zebra))
    assert not zebra.pc.is_armed()

    zebra.pc.arm.arm_set.set = mock_disarm

    with pytest.raises(Exception):
        zebra.pc.arm.armed.set(0)
        RE(arm_zebra(zebra, 0.2))
    with pytest.raises(Exception):
        zebra.pc.arm.armed.set(1)
        RE(disarm_zebra(zebra, 0.2))
