import time

import bluesky.preprocessors as bpp
from bluesky.plan_stubs import null, rd

from artemis.devices.flux_calculator import FluxCalculator
from artemis.flux_parameters import FluxCalculationParameters, FluxPredictionParameters


def get_flux(parameters: FluxCalculationParameters):
    flux_calculator = FluxCalculator(name="Flux calculator", prefix=parameters.beamline)
    flux_calculator.wait_for_connection()
    flux_calculator.aperture_size_signal.put(parameters.aperture_size)
    return flux_calculator.get_flux()


@bpp.run_decorator()
def flux_calculation_plan(flux_calculator: FluxCalculator):
    flux_calculation_value = yield from rd(flux_calculator)
    print(f"{flux_calculation_value=}")


def get_flux_calculation_plan(parameters: FluxCalculationParameters):
    flux_calculator = FluxCalculator(
        name="Flux calculator", prefix=parameters.beamline, read_attrs=["flux"]
    )
    flux_calculator.wait_for_connection(all_signals=True)
    flux_calculator.aperture_size_signal.put(parameters.aperture_size)
    time.sleep(0.1)
    return flux_calculation_plan(flux_calculator)


def predict_flux(parameters: FluxPredictionParameters):
    # predicts flux based on expected 100% beam value given energy, ring current, aperture and transmission
    energy = parameters.energy

    A = -2.104798686e-15
    B = 1.454341082e-10
    C = 3.586744314e-6
    D = 3.599085792e-2
    E = 1.085096504e2

    predicted_flux = (
        (parameters.ring_current / 300)
        * parameters.aperture_size
        * parameters.transmission
        * (A * energy**4 + B * energy**3 - C * energy**2 + D * energy - E)
        * 1e12
    )
    return predicted_flux


def get_flux_prediction_plan(parameters):
    return null()
