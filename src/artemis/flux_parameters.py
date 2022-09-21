from dataclasses_json import dataclass_json
from pydantic.dataclasses import dataclass as pydantic_dataclass


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
