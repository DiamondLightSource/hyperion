from unittest.mock import patch

from artemis.flux_parameters import FluxCalculationParameters, FluxPredictionParameters
from artemis.flux_plan import get_flux, predict_flux

TEST_BEAMLINE = "BL03S"
TEST_APERTURE_SIZE = 1
TEST_ENERGY = 10000
TEST_TRANSMISSION = 1
TEST_RING_CURRENT = 300


def dummy_flux_calculation_params():
    return FluxCalculationParameters(
        beamline=TEST_BEAMLINE, aperture_size=TEST_APERTURE_SIZE
    )


def dummy_flux_prediction_parameters(
    aperture_size=TEST_APERTURE_SIZE,
    energy=TEST_ENERGY,
    transmission=TEST_TRANSMISSION,
    ring_current=TEST_RING_CURRENT,
):
    return FluxPredictionParameters(
        aperture_size,
        energy,
        transmission,
        ring_current,
    )


def test_get_flux_waits_for_connection():
    with patch("artemis.flux_plan.FluxCalculator") as mock_flux_calculator:
        mock_calc = mock_flux_calculator.return_value
        get_flux(dummy_flux_calculation_params())
        mock_calc.wait_for_connection.assert_called_once()


def test_get_flux_sets_aperture_size_on_flux_calculator():
    with patch("artemis.flux_plan.FluxCalculator") as mock_flux_calculator:
        mock_calc = mock_flux_calculator.return_value
        get_flux(dummy_flux_calculation_params())
        mock_calc.aperture_size_signal.put.assert_called_once_with(TEST_APERTURE_SIZE)


A = -2.104798686e-15
B = 1.454341082e-10
C = 3.586744314e-6
D = 3.599085792e-2
E = 1.085096504e2


def test_predict_flux_returns_correct_values_for_known_input():
    result = predict_flux(dummy_flux_prediction_parameters())
    energy = TEST_ENERGY
    expected_result = (
        TEST_RING_CURRENT
        * TEST_APERTURE_SIZE
        * TEST_TRANSMISSION
        * (A * energy**4 + B * energy**3 - C * energy**2 + D * energy - E)
        * 1e12
        / 300
    )
    assert result == expected_result
