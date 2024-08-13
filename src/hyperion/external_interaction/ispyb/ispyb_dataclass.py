from enum import Enum
from typing import Optional

from pydantic import BaseModel


class IspybParams(BaseModel):
    visit_path: str

    # Optional from GDA as populated by Ophyd
    xtal_snapshots_omega_start: Optional[list[str]] = None


class RotationIspybParams(IspybParams): ...


class GridscanIspybParams(IspybParams): ...


class Orientation(Enum):
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"
