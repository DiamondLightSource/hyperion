import pytest
from ophyd.sim import make_fake_device

from artemis.devices.aperture import Aperture


@pytest.fixture
def fake_aperture():
    FakeAperture = make_fake_device(Aperture)
    fake_aperture: Aperture = FakeAperture(name="aperture")
    return fake_aperture


def test_aperture_can_be_created(fake_aperture: Aperture):
    fake_aperture.wait_for_connection()
