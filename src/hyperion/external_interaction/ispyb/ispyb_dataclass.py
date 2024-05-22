from enum import Enum
from typing import Any, Dict, Optional

import numpy as np
from pydantic import BaseModel, validator

GRIDSCAN_ISPYB_PARAM_DEFAULTS = {
    "sample_id": None,
    "visit_path": "",
    "position": [0, 0, 0],
    "xtal_snapshots_omega_start": ["test_1_y", "test_2_y", "test_3_y"],
    "xtal_snapshots_omega_end": ["test_1_z", "test_2_z", "test_3_z"],
    "comment": "Descriptive comment.",
}


class IspybParams(BaseModel):
    visit_path: str
    position: np.ndarray
    comment: str
    sample_id: Optional[int] = None

    # Optional from GDA as populated by Ophyd
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


class RobotLoadIspybParams(IspybParams): ...


class RotationIspybParams(IspybParams): ...


class GridscanIspybParams(IspybParams):
    def dict(self, **kwargs):
        as_dict = super().dict(**kwargs)
        return as_dict


class Orientation(Enum):
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"
