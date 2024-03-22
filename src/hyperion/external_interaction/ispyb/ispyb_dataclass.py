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
    # populated by wait_for_robot_load_then_centre
    current_energy_ev: Optional[float]
    beam_size_x: float
    beam_size_y: float
    focal_spot_size_x: float
    focal_spot_size_y: float
    comment: str
    # populated by wait_for_robot_load_then_centre
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
    def dict(self, **kwargs):
        as_dict = super().dict(**kwargs)
        return as_dict


class Orientation(Enum):
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"
