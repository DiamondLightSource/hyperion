from unittest.mock import MagicMock

import pytest
from ophyd.sim import make_fake_device

from artemis.devices.dcm import DCM
from artemis.devices.flux_calculator import FluxCalculator
from artemis.devices.xbpm2 import XBPM2

A = 5.393959225e-13
B = 1.321301118e-8
C = 4.768760712e-4
D = 2.118311635


def dummy_dcm(energy: float):
    FakeDCM = make_fake_device(DCM)
    fake_dcm: DCM = FakeDCM(name="DCM")
    fake_dcm.energy_rbv.get = MagicMock(return_value=energy)
    return fake_dcm


def dummy_xbpm2(intensity: float):
    FakeXBPM2 = make_fake_device(XBPM2)
    fake_xbpm2: XBPM2 = FakeXBPM2(name="XBPM2")
    fake_xbpm2.intensity.get = MagicMock(return_value=intensity)
    return fake_xbpm2


@pytest.mark.parametrize(
    "energy, intensity, aperture_size, expected_result",
    [
        (1 / 1000, 1e-6, 1, 1e12 * (A - B + C - D)),
        (2 / 1000, 1e-6, 1, 1e12 * (A * 8 - B * 4 + C * 2 - D)),
        (1 / 1000, 1e-18, 1, (A - B + C - D)),
        (1 / 1000, 1e-6, 1e-12, (A - B + C - D)),
    ],
)
def test_get_flux_returns_correct_values_for_known_input(
    energy, intensity, aperture_size, expected_result
):
    flux_calculator = FluxCalculator(prefix="BL03S", name="flux calculator")
    flux_calculator.aperture_size_signal.put(aperture_size)
    flux_calculator.dcm = dummy_dcm(energy)
    flux_calculator.xbpm2 = dummy_xbpm2(intensity)
    flux_result = flux_calculator.get_flux()
    assert flux_result == pytest.approx(expected_result, rel=1e-12)
