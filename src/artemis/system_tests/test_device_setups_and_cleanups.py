import pytest
from bluesky.run_engine import RunEngine
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

from artemis.device_setup_plans.setup_zebra_for_fgs import (
    set_zebra_shutter_to_manual,
    setup_zebra_for_fgs,
)
from artemis.device_setup_plans.setup_zebra_for_rotation import setup_zebra_for_rotation


@pytest.fixture
def RE():
    return RunEngine({})


@pytest.fixture
def connected_zebra():
    zebra = Zebra(name="zebra", prefix="BL03S-EA-ZEBRA-01:")
    zebra.wait_for_connection()
    return zebra


@pytest.mark.s03
def test_zebra_set_up_for_fgs(RE, connected_zebra: Zebra):
    RE(setup_zebra_for_fgs(connected_zebra))
    assert connected_zebra.output.out_pvs[TTL_DETECTOR].get() == IN3_TTL
    assert connected_zebra.output.out_pvs[TTL_SHUTTER].get() == IN4_TTL


@pytest.mark.s03
def test_zebra_set_up_for_rotation(RE, connected_zebra: Zebra):
    RE(setup_zebra_for_rotation(connected_zebra))
    assert connected_zebra.pc.gate_trigger.get(as_string=True) == I03_axes.OMEGA.value
    assert connected_zebra.pc.gate_width.get() == pytest.approx(360, 0.01)


@pytest.mark.s03
def test_zebra_cleanup(RE, connected_zebra: Zebra):
    RE(set_zebra_shutter_to_manual(connected_zebra))
    assert connected_zebra.output.out_pvs[TTL_DETECTOR].get() == PC_PULSE
    assert connected_zebra.output.out_pvs[TTL_SHUTTER].get() == OR1
