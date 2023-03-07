from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from dataclasses_json import config, dataclass_json

from artemis.utils import Point3D

ISPYB_PARAM_DEFAULTS = {
    "sample_id": None,
    "sample_barcode": None,
    "visit_path": "",
    "pixels_per_micron_x": 0.0,
    "pixels_per_micron_y": 0.0,
    # gets stored as 2x2D coords - (x, y) and (x, z). Values in pixels
    "upper_left": Point3D(x=0, y=0, z=0),
    "position": Point3D(x=0, y=0, z=0),
    "xtal_snapshots_omega_start": ["test_1_y", "test_2_y", "test_3_y"],
    "xtal_snapshots_omega_end": ["test_1_z", "test_2_z", "test_3_z"],
    "transmission": 1.0,
    "flux": 10.0,
    "wavelength": 0.01,
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


@dataclass_json
@dataclass
class IspybParams:
    visit_path: str
    pixels_per_micron_x: float
    pixels_per_micron_y: float

    upper_left: Point3D = field(
        # in px on the image
        metadata=config(
            encoder=lambda mytuple: mytuple._asdict(),
            decoder=lambda mydict: Point3D(**mydict),
        )
    )

    position: Point3D = field(
        # motor position
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
