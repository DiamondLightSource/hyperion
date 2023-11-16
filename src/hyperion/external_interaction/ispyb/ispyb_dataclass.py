from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np
from pydantic import BaseModel, validator

from hyperion.parameters.external_parameters import ExternalParameters
from hyperion.utils.utils import convert_eV_to_angstrom

GRIDSCAN_ISPYB_PARAM_DEFAULTS = {
    "sample_id": None,
    "sample_barcode": None,
    "visit_path": "",
    "microns_per_pixel_x": 0.0,
    "microns_per_pixel_y": 0.0,
    "current_energy_ev": 12700,
    # gets stored as 2x2D coords - (x, y) and (x, z). Values in pixels
    "upper_left": [0, 0, 0],
    "position": [0, 0, 0],
    "xtal_snapshots_omega_start": ["test_1_y", "test_2_y", "test_3_y"],
    "xtal_snapshots_omega_end": ["test_1_z", "test_2_z", "test_3_z"],
    "transmission_fraction": 1.0,
    "flux": 10.0,
    "beam_size_x": 0.1,
    "beam_size_y": 0.1,
    "focal_spot_size_x": 0.0,
    "focal_spot_size_y": 0.0,
    "comment": "Descriptive comment.",
    "resolution": 1,
    "undulator_gap": 1.0,
    "synchrotron_mode": None,
    "slit_gap_size_x": 0.1,
    "slit_gap_size_y": 0.1,
}


class IspybParams(BaseModel):
    visit_path: str
    microns_per_pixel_x: float
    microns_per_pixel_y: float
    position: np.ndarray

    @classmethod
    def from_external(cls, external: ExternalParameters):
        data_dict = external.data_parameters.dict()
        expt = external.experiment_parameters
        experiment_dict = expt.dict()
        data_dict["position"] = [
            expt.x_start_mm or expt.x or 0,
            expt.y1_start_mm or expt.y or 0,
            expt.z1_start_mm or expt.z or 0,
        ]
        return cls(**data_dict, **experiment_dict)

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {np.ndarray: lambda a: a.tolist()}

    def dict(self, **kwargs):
        as_dict = super().dict(**kwargs)
        as_dict["position"] = as_dict["position"].tolist()
        return as_dict

    @validator("position", always=True, pre=True)
    def _parse_position(
        cls, position: list[int | float] | np.ndarray, values: Dict[str, Any]
    ) -> np.ndarray:
        assert len(position) == 3
        if isinstance(position, np.ndarray):
            return position
        return np.array(position)

    transmission_fraction: float
    current_energy_ev: float
    beam_size_x_mm: float
    beam_size_y_mm: float
    focal_spot_size_x_mm: float
    focal_spot_size_y_mm: float
    comment: str
    resolution: float

    sample_id: Optional[int] = None
    sample_barcode: Optional[str] = None

    # Optional from GDA as populated by Ophyd
    flux: Optional[float] = None
    undulator_gap: Optional[float] = None
    synchrotron_mode: Optional[str] = None
    slit_gap_size_x: Optional[float] = None
    slit_gap_size_y: Optional[float] = None
    xtal_snapshots_omega_start: Optional[List[str]] = None
    xtal_snapshots_omega_end: Optional[List[str]] = None

    @validator("transmission_fraction")
    def _transmission_not_percentage(cls, transmission_fraction: float):
        if transmission_fraction > 1:
            raise ValueError(
                "Transmission_fraction of >1 given. Did you give a percentage instead of a fraction?"
            )
        return transmission_fraction

    @property
    def wavelength_angstroms(self):
        return convert_eV_to_angstrom(self.current_energy_ev)


class RotationIspybParams(IspybParams):
    ...


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
