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

from artemis.device_setup_plans.setup_zebra import (
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
    RE(setup_zebra_for_fgs(zebra))
    assert zebra.output.out_pvs[TTL_DETECTOR].get() == IN3_TTL
    assert zebra.output.out_pvs[TTL_SHUTTER].get() == IN4_TTL


@pytest.mark.s03
def test_zebra_set_up_for_rotation(RE, zebra: Zebra):
    RE(setup_zebra_for_rotation(zebra))
    assert zebra.pc.gate_trigger.get(as_string=True) == I03_axes.OMEGA.value
    assert zebra.pc.gate_width.get() == pytest.approx(360, 0.01)


@pytest.mark.s03
def test_zebra_cleanup(RE, zebra: Zebra):
    RE(set_zebra_shutter_to_manual(zebra))
    assert zebra.output.out_pvs[TTL_DETECTOR].get() == PC_PULSE
    assert zebra.output.out_pvs[TTL_SHUTTER].get() == OR1
