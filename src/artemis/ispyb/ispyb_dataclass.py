from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from dataclasses_json import config, dataclass_json
from artemis.utils import Point3D



@dataclass_json
@dataclass
class IspybParams:
    visit_path: str
    pixels_per_micron_x: float
    pixels_per_micron_y: float

    upper_left: Point3D = field(
        metadata=config(
            encoder=lambda mytuple: mytuple._asdict(),
            decoder=lambda mydict: Point3D(**mydict),
        )
    )

    position: Point3D = field(
        metadata=config(
            encoder=lambda mytuple: mytuple._asdict(),
            decoder=lambda mydict: Point3D(**mydict),
        )
    )

    xtal_snapshots_omega_start: List[str]
    xtal_snapshots_omega_end: List[str]
    transmission: float
    flux: float
    wavelength: float
    beam_size_x: float
    beam_size_y: float
    focal_spot_size_x: float
    focal_spot_size_y: float
    comment: str
    resolution: float

    sample_id: Optional[int] = None
    sample_barcode: Optional[str] = None

    # Optional from GDA as populated by Ophyd
    undulator_gap: Optional[float] = None
    synchrotron_mode: Optional[str] = None
    slit_gap_size_x: Optional[float] = None
    slit_gap_size_y: Optional[float] = None


class Orientation(Enum):
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"
