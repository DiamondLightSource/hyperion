from enum import Enum
from typing import Any, Dict, Optional

import numpy as np
from pydantic import BaseModel, validator

from hyperion.utils.utils import convert_eV_to_angstrom

GRIDSCAN_ISPYB_PARAM_DEFAULTS = {
    "sample_id": None,
    "visit_path": "",
    "microns_per_pixel_x": 0.0,
    "microns_per_pixel_y": 0.0,
    "current_energy_ev": None,
    # gets stored as 2x2D coords - (x, y) and (x, z). Values in pixels
    "upper_left": [0, 0, 0],
    "position": [0, 0, 0],
    "xtal_snapshots_omega_start": ["test_1_y", "test_2_y", "test_3_y"],
    "xtal_snapshots_omega_end": ["test_1_z", "test_2_z", "test_3_z"],
    "transmission_fraction": None,
    "flux": None,
    "beam_size_x": 0.1,
    "beam_size_y": 0.1,
    "focal_spot_size_x": 0.0,
    "focal_spot_size_y": 0.0,
    "comment": "Descriptive comment.",
    "resolution": 1,
    "undulator_gap": None,
}


class IspybParams(BaseModel):
    visit_path: str
    microns_per_pixel_x: float
    microns_per_pixel_y: float
    position: np.ndarray

    transmission_fraction: Optional[float]  # TODO 1033 this is now deprecated
    # populated by robot_load_then_centre
    current_energy_ev: Optional[float]
    beam_size_x: float
    beam_size_y: float
    focal_spot_size_x: float
    focal_spot_size_y: float
    comment: str
    # populated by robot_load_then_centre
    resolution: Optional[float]

    sample_id: Optional[str] = None

    # Optional from GDA as populated by Ophyd
    flux: Optional[float] = None
    undulator_gap: Optional[float] = None
    xtal_snapshots_omega_start: Optional[list[str]] = None
    xtal_snapshots_omega_end: Optional[list[str]] = None

    ispyb_experiment_type: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {np.ndarray: lambda a: a.tolist()}

    def dict(self, **kwargs):
        as_dict = super().dict(**kwargs)
        as_dict["position"] = as_dict["position"].tolist()
        return as_dict

    @validator("position", pre=True)
    def _parse_position(
        cls, position: list[int | float] | np.ndarray, values: Dict[str, Any]
    ) -> np.ndarray:
        assert len(position) == 3
        if isinstance(position, np.ndarray):
            return position
        return np.array(position)

    @validator("transmission_fraction")
    def _transmission_not_percentage(cls, transmission_fraction: Optional[float]):
        if transmission_fraction and transmission_fraction > 1:
            raise ValueError(
                "Transmission_fraction of >1 given. Did you give a percentage instead of a fraction?"
            )
        return transmission_fraction

    @property
    def wavelength_angstroms(self) -> Optional[float]:
        if self.current_energy_ev:
            return convert_eV_to_angstrom(self.current_energy_ev)
        return None  # Return None instead of 0 in order to avoid overwriting previously written values


class RobotLoadIspybParams(IspybParams): ...


class RotationIspybParams(IspybParams): ...


class GridscanIspybParams(IspybParams):
    upper_left: np.ndarray

    def dict(self, **kwargs):
        as_dict = super().dict(**kwargs)
        as_dict["upper_left"] = as_dict["upper_left"].tolist()
        return as_dict

    @validator("upper_left", pre=True)
    def _parse_upper_left(
        cls, upper_left: list[int | float] | np.ndarray, values: Dict[str, Any]
    ) -> np.ndarray:
        assert len(upper_left) == 3
        if isinstance(upper_left, np.ndarray):
            return upper_left
        return np.array(upper_left)


class Orientation(Enum):
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"
