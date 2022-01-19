import pytest

from src.artemis.devices.zebra import Zebra, PositionCompare


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
    assert zebra.pc.is_armed()


@pytest.mark.s03
def test_zebra_unstage(zebra: Zebra):
    zebra.unstage()
    assert not zebra.pc.is_armed()
