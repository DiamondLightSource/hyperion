from contextlib import nullcontext

import pytest
from pydantic.error_wrappers import ValidationError

from artemis.flux_parameters import FluxCalculationParameters, FluxPredictionParameters


@pytest.mark.parametrize(
    "aperture_size, error_expected", [(0.5, False), ("test", True)]
)
def test_flux_calculation_parameters_validates_aperture_size_type(
    aperture_size, error_expected
):
    with pytest.raises(ValidationError) if error_expected else nullcontext():
        FluxCalculationParameters(aperture_size=aperture_size)


@pytest.mark.parametrize(
    "aperture_size, error_expected", [(0.5, False), (-1, True), (1.1, True)]
)
def test_flux_calculation_parameters_validates_aperture_size_value(
    aperture_size, error_expected
):
    with pytest.raises(ValueError) if error_expected else nullcontext():
        FluxCalculationParameters(aperture_size=aperture_size)


@pytest.mark.parametrize(
    "aperture_size, error_expected", [(0.5, False), ("test", True)]
)
def test_flux_prediction_parameters_validates_types(aperture_size, error_expected):
    with pytest.raises(ValidationError) if error_expected else nullcontext():
        FluxPredictionParameters(aperture_size=aperture_size)


@pytest.mark.parametrize(
    "aperture_size, error_expected", [(0.5, False), (-1, True), (1.1, True)]
)
def test_flux_prediction_parameters_validates_aperture_size_value(
    aperture_size, error_expected
):
    with pytest.raises(ValueError) if error_expected else nullcontext():
        FluxPredictionParameters(aperture_size=aperture_size)


@pytest.mark.parametrize(
    "energy, error_expected", [(10000, False), (5000, True), (30000, True)]
)
def test_flux_prediction_parameters_validates_energy_value(energy, error_expected):
    with pytest.raises(ValueError) if error_expected else nullcontext():
        FluxPredictionParameters(energy=energy)


@pytest.mark.parametrize(
    "transmission, error_expected", [(0.5, False), (-1, True), (1.1, True)]
)
def test_flux_prediction_parameters_validates_transmission_value(
    transmission, error_expected
):
    with pytest.raises(ValueError) if error_expected else nullcontext():
        FluxPredictionParameters(transmission=transmission)


@pytest.mark.parametrize(
    "ring_current, error_expected", [(100, False), (1, True), (500, True)]
)
def test_flux_prediction_parameters_validates_ring_current_value(
    ring_current, error_expected
):
    with pytest.raises(ValueError) if error_expected else nullcontext():
        FluxPredictionParameters(ring_current=ring_current)
