import pytest
from ophyd.sim import make_fake_device

from artemis.devices.dcm import DCM


@pytest.fixture
def fake_dcm():
    FakeDCM = make_fake_device(DCM)
    fake_dcm: DCM = FakeDCM(name="dcm")
    return fake_dcm


def test_dcm_can_be_created(fake_dcm: DCM):
    fake_dcm.wait_for_connection()
