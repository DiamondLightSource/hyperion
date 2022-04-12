from dataclasses import dataclass, field
from collections import namedtuple
from enum import Enum

from dataclasses_json import dataclass_json, config

Point2D = namedtuple("point_2d", ["x", "y"])
Point3D = namedtuple("point_3d", ["x", "y", "z"])


@dataclass_json
@dataclass
class IspybParams:
    sample_id: int
    visit_path: str
    undulator_gap: float
    pixels_per_micron_x: float
    pixels_per_micron_y: float

    upper_left: Point2D = field(
        metadata=config(
            encoder=lambda mytuple: mytuple._asdict(),
            decoder=lambda mydict: Point2D(**mydict),
        )
    )

    sample_barcode: str

    position: Point3D = field(
        metadata=config(
            encoder=lambda mytuple: mytuple._asdict(),
            decoder=lambda mydict: Point3D(**mydict),
        )
    )

    synchrotron_mode: str
    xtal_snapshots: str
    run_number: int
    transmission: float
    flux: float
    wavelength: float
    beam_size_x: float
    beam_size_y: float
    slit_gap_size_x: float
    slit_gap_size_y: float
    focal_spot_size_x: float
    focal_spot_size_y: float
    comment: str
    resolution: float


class Orientation(Enum):
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"
