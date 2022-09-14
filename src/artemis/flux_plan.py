from enum import Enum

from dataclasses_json import dataclass_json
from pydantic.dataclasses import dataclass as pydantic_dataclass

from artemis.devices.flux_calculator import FluxCalculator


class scale(Enum):
    # aperture scales to be applied to XBPM2 reading to give flux at sample
    Large = 0.738
    Medium = 0.336
    Small = 0.084
    Empty = 1


@dataclass_json
@pydantic_dataclass
class FluxCalculationParameters:
    beamline: str = "BL03S"
    aperture_size: float = 0.738

    def _validate_values(self):
        if not (0 <= self.aperture_size <= 1):
            raise ValueError(
                f"Aperture size should be between 0 and 1, not {self.aperture_size}"
            )

    def __post_init_post_parse__(self):
        self._validate_values()


def get_flux(parameters: FluxCalculationParameters):
    flux_calculator = FluxCalculator(name="Flux calculator", prefix=parameters.beamline)
    flux_calculator.wait_for_connection()
    flux_calculator.aperture_size_signal.put(parameters.aperture_size)
    return flux_calculator.get_flux()


@dataclass_json
@pydantic_dataclass
class FluxPredictionParameters:
    aperture_size: float = 0.738
    energy: float = 12700
    transmission: float = 1
    ring_current: float = 300

    def _validate_values(self):
        if not (0 <= self.aperture_size <= 1):
            raise ValueError(
                f"Aperture size should be between 0 and 1, not {self.aperture_size}"
            )
        if not (5500 < self.energy < 25000):
            raise ValueError(
                f"Energy (eV) valid range is 5500-25000, not {self.energy}"
            )
        if not (0 <= self.transmission <= 1):
            raise ValueError(
                f"Transmission should be in fractional notation, between 0 and 1, "
                f"not {self.aperture_size}"
            )
        if not (10 <= self.ring_current <= 400):
            raise ValueError(
                f"Ring Current (mA) valid range is 10-400, not {self.ring_current}"
            )

    def __post_init_post_parse__(self):
        self._validate_values()


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
