from unittest.mock import MagicMock, patch

import pytest

from artemis.devices.flux_calculator import FluxCalculator

A = 5.393959225e-13
B = 1.321301118e-8
C = 4.768760712e-4
D = 2.118311635


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
    flux_calculator = FluxCalculator(prefix="BL03I", name="flux calculator")
    flux_calculator.aperture_size_signal.put(aperture_size)
    mock_energy_get = MagicMock(get=MagicMock(return_value=energy))
    mock_intensity_get = MagicMock(get=MagicMock(return_value=intensity))
    with patch.object(FluxCalculator, "energy_signal", mock_energy_get), patch.object(
        FluxCalculator, "intensity_signal", mock_intensity_get
    ):
        flux_result = flux_calculator.get_flux()
    assert flux_result == pytest.approx(expected_result, rel=1e-12)
