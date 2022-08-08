import pytest
from ophyd.sim import make_fake_device

from src.artemis.devices.backlight import Backlight


@pytest.fixture
def fake_backlight():
    FakeBacklight = make_fake_device(Backlight)
    fake_backlight: Backlight = FakeBacklight(name="backlight")
    return fake_backlight


def test_backlight_can_be_written_and_read_from(fake_backlight: Backlight):
    fake_backlight.pos.sim_put(fake_backlight.IN)
    assert fake_backlight.pos.get() == fake_backlight.IN
