import pytest

from src.artemis.devices.zebra import (
    Zebra,
    TTL_DETECTOR,
    TTL_SHUTTER,
    PC_PULSE,
    OR1,
    IN3_TTL,
    IN4_TTL,
)


@pytest.fixture()
def zebra():
    zebra = Zebra(name="zebra", prefix="BL03S-EA-ZEBRA-01:")
    yield zebra
    zebra.pc.disarm().wait(10.0)


@pytest.mark.s03
def test_arm(zebra: Zebra):
    assert not zebra.pc.is_armed()
    zebra.pc.arm().wait(10.0)
    assert zebra.pc.is_armed()
    zebra.pc.disarm().wait(10.0)


@pytest.mark.s03
def test_disarm(zebra: Zebra):
    zebra.pc.arm().wait(10.0)
    assert zebra.pc.is_armed()
    zebra.pc.disarm().wait(10.0)
    assert not zebra.pc.is_armed()


@pytest.mark.s03
def test_zebra_stage(zebra: Zebra):
    zebra.stage()
    assert zebra.output.out_pvs[TTL_DETECTOR].get() == IN3_TTL
    assert zebra.output.out_pvs[TTL_SHUTTER].get() == IN4_TTL


@pytest.mark.s03
def test_zebra_unstage(zebra: Zebra):
    zebra.unstage()
    assert zebra.output.out_pvs[TTL_DETECTOR].get() == PC_PULSE
    assert zebra.output.out_pvs[TTL_SHUTTER].get() == OR1
