from dataclasses import dataclass
from collections import namedtuple
from enum import Enum

Point2D = namedtuple('Point2D', ['x', 'y'])
Point3D = namedtuple('Point3D', ['x', 'y', 'z'])

@dataclass
class IspybParams:
    sample_id: int
    visit_path: str
    undulator_gap: float
    pixels_per_micron_x: float
    pixels_per_micron_y: float
    upper_left: Point2D
    bottom_right: Point2D
    sample_barcode: str
    position: Point3D
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