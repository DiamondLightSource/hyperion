import pytest
from bluesky.run_engine import RunEngine
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

from hyperion.device_setup_plans.setup_zebra import (
    set_zebra_shutter_to_manual,
    setup_zebra_for_gridscan,
    setup_zebra_for_rotation,
)


@pytest.fixture
async def connected_zebra():
    RunEngine()
    zebra = Zebra(name="zebra", prefix="BL03S-EA-ZEBRA-01:")
    await zebra.connect()
    return zebra


@pytest.mark.s03
async def test_zebra_set_up_for_gridscan(RE, connected_zebra: Zebra):
    RE(setup_zebra_for_gridscan(connected_zebra, wait=True))
    assert await connected_zebra.output.out_pvs[TTL_DETECTOR].get_value() == IN3_TTL
    assert await connected_zebra.output.out_pvs[TTL_SHUTTER].get_value() == IN4_TTL


@pytest.mark.s03
async def test_zebra_set_up_for_rotation(RE, connected_zebra: Zebra):
    RE(setup_zebra_for_rotation(connected_zebra, wait=True))
    assert await connected_zebra.pc.gate_trigger.get_value() == I03Axes.OMEGA.value
    assert await connected_zebra.pc.gate_width.get_value() == pytest.approx(360, 0.01)


@pytest.mark.s03
async def test_zebra_cleanup(RE, connected_zebra: Zebra):
    RE(set_zebra_shutter_to_manual(connected_zebra, wait=True))
    assert await connected_zebra.output.out_pvs[TTL_DETECTOR].get_value() == PC_PULSE
    assert await connected_zebra.output.out_pvs[TTL_SHUTTER].get_value() == OR1
