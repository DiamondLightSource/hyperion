import pytest
from ophyd.sim import make_fake_device

from artemis.devices.xbpm2 import XBPM2


@pytest.fixture
def fake_xbpm2():
    FakeXBPM2 = make_fake_device(XBPM2)
    fake_xbpm2: XBPM2 = FakeXBPM2(name="xbpm2")
    return fake_xbpm2


def test_xbpm2_can_be_created(fake_xbpm2: XBPM2):
    fake_xbpm2.wait_for_connection()
