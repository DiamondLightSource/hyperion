from enum import Enum

import bluesky.plan_stubs as bps
from bluesky import Msg, RunEngine

from artemis.devices.dcm import DCM
from artemis.devices.xbpm2 import XBPM2

RE = RunEngine({})

xbpm2 = XBPM2(name="XBPM2", prefix="BL03I")
dcm = DCM(name="DCM", prefix="BL03I")

xbpm2.wait_for_connection()
dcm.wait_for_connection()


class scale(Enum):
    # aperture scales to be applied to XBPM2 reading to give flux at sample
    Large = 0.738
    Medium = 0.336
    Small = 0.084
    Empty = 1


def get_flux(aperture_size="Large"):
    # get live flux for data collection, needs aperture specified

    valid = {"Large", "Medium", "Small", "Empty"}
    if aperture_size not in valid:
        raise ValueError("Aperture size must be one of %r," % valid)

    class scale(Enum):
        Large = 0.738
        Medium = 0.336
        Small = 0.084
        Empty = 1

    aperture_scale = float(scale[aperture_size].value)

    # polynomial fit coefficients for XBPM2 response to energy
    A = 5.393959225e-13
    B = 1.321301118e-8
    C = 4.768760712e-4
    D = 2.118311635
    E = (yield from bps.rd(dcm.energy)) * 1000

    gradient = A * E**3 - B * E**2 + C * E - D

    signal = (yield from bps.rd(xbpm2.intensity)) / 1e-6

    flux = float(1e12 * signal * gradient)

    flux_at_sample = "{:e}".format(flux * aperture_scale)

    print(f"{flux_at_sample=}")

    # how to do return values on functions that require runengine?


def predict_flux(aperture_size="Large", energy=12700, transmission=1, ring_current=300):
    yield Msg("open_run")
    # predicts flux based on expected 100% beam value given energy, ring current, aperture and transmission
    valid_aperture = {"Large", "Medium", "Small", "Empty"}

    # move to validate functions
    if aperture_size not in valid_aperture:
        raise ValueError("Aperture size must be one of %r," % valid_aperture)
    if energy <= 5500 or energy >= 25000:
        raise ValueError("Energy is required in eV and in range 5500 to 25000eV")
    if transmission < 0 or transmission > 1:
        raise ValueError(
            "Transmission should be in fractional notation, between 0 and 1"
        )
    if ring_current < 10 or ring_current > 400:
        raise ValueError("Ring Current (mA) valid range is 10-400")

    aperture_scale = float(scale[aperture_size].value)
    energy_eV = float(energy)
    transmission_scale = float(transmission)
    ring_current_scale = ring_current / 300

    print(f"{aperture_scale=}")
    print(f"{energy=}")
    print(f"{transmission=}")

    A = -2.104798686e-15
    B = 1.454341082e-10
    C = 3.586744314e-6
    D = 3.599085792e-2
    E = 1.085096504e2

    predicted_flux = "{:e}".format(
        ring_current_scale
        * aperture_scale
        * transmission_scale
        * (
            A * energy_eV**4
            + B * energy_eV**3
            - C * energy_eV**2
            + D * energy_eV
            - E
        )
        * 1e12
    )
    print(f"{predicted_flux=}")
    yield Msg("close_run")


if __name__ == "__main__":
    predicted_flux = predict_flux("Large", 12700, 1, 300)
    print(f"Prediction: {predicted_flux}")
