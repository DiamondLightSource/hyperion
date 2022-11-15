import pytest

from artemis.devices.zebras.FGSzebra import FGSZebra
from artemis.devices.zebras.zebra_base import (
    IN3_TTL,
    IN4_TTL,
    OR1,
    PC_PULSE,
    TTL_DETECTOR,
    TTL_SHUTTER,
)


@pytest.fixture()
def zebra():
    zebra = FGSZebra(name="zebra", prefix="BL03S-EA-ZEBRA-01:")
    yield zebra
    zebra.pc.disarm().wait(10.0)


@pytest.mark.s03
def test_arm(zebra: FGSZebra):
    assert not zebra.pc.is_armed()
    zebra.pc.arm().wait(10.0)
    assert zebra.pc.is_armed()
    zebra.pc.disarm().wait(10.0)


@pytest.mark.s03
def test_disarm(zebra: FGSZebra):
    zebra.pc.arm().wait(10.0)
    assert zebra.pc.is_armed()
    zebra.pc.disarm().wait(10.0)
    assert not zebra.pc.is_armed()


@pytest.mark.s03
def test_zebra_stage(zebra: FGSZebra):
    zebra.stage()
    assert zebra.output.out_pvs[TTL_DETECTOR].get() == IN3_TTL
    assert zebra.output.out_pvs[TTL_SHUTTER].get() == IN4_TTL


@pytest.mark.s03
def test_zebra_unstage(zebra: FGSZebra):
    zebra.unstage()
    assert zebra.output.out_pvs[TTL_DETECTOR].get() == PC_PULSE
    assert zebra.output.out_pvs[TTL_SHUTTER].get() == OR1
