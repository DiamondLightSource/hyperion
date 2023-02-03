import pytest
from bluesky.run_engine import RunEngine
from dodal.devices.zebra import (
    IN3_TTL,
    IN4_TTL,
    OR1,
    PC_PULSE,
    TTL_DETECTOR,
    TTL_SHUTTER,
    Zebra,
)

from artemis.device_setup_plans.setup_zebra_for_fgs import (
    set_zebra_shutter_to_manual,
    setup_zebra_for_fgs,
)


@pytest.fixture
def RE():
    return RunEngine({})


@pytest.mark.s03
def test_zebra_set_up(RE):
    zebra = Zebra(name="zebra", prefix="BL03S-EA-ZEBRA-01:")
    RE(setup_zebra_for_fgs(zebra))
    assert zebra.output.out_pvs[TTL_DETECTOR].get() == IN3_TTL
    assert zebra.output.out_pvs[TTL_SHUTTER].get() == IN4_TTL


@pytest.mark.s03
def test_zebra_cleanup(RE):
    zebra = Zebra(name="zebra", prefix="BL03S-EA-ZEBRA-01:")
    RE(set_zebra_shutter_to_manual(zebra))
    assert zebra.output.out_pvs[TTL_DETECTOR].get() == PC_PULSE
    assert zebra.output.out_pvs[TTL_SHUTTER].get() == OR1
