from dataclasses import dataclass
from enum import Enum


class Orientation(Enum):
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"


@dataclass
class GridInfo:
    ispyb_data_collection_id: int
    dx_mm: float
    dy_mm: float
    steps_x: int
    steps_y: int
    pixels_per_micron_x: float
    pixels_per_micron_y: float
    snapshot_offset_pixel_x: float
    snapshot_offset_pixel_y: float
    orientation: Orientation
    snaked: bool


@dataclass
class DataCollection:
    data_collection_group_id: int # required
    sample_id: int
    position_id: int
    detector_id: int
    visit: str
    axis_start: int
    axis_end: int
    axis_range: int
    focal_spot_size_at_sample_x: int
    focal_spot_size_at_sample_y: int
    slitgap_vertical: float
    slitgap_horizontal: float
    beamsize_at_sample_x: float
    beamsize_at_sample_y: float
    transmission: float
    comments: str
    data_collection_number: int
    detector_distance: float
    exposure_time: float
    img_dir: str
    img_prefix: str
    img_suffix: str
    number_of_images: int
    number_of_passes: int
    overlap: float
    flux: float
    omega_start: float
    start_image_number: int
    resolution: float
    wavelength: float
    x_beam: float
    y_beam: float
    xtal_snapshots_1: str
    xtal_snapshots_2: str
    xtal_snapshots_3: str
    synchrotron_mode: str
    undulator_gap: float
    start_time: str # db column is datetime, so needs to be a string of the format YYYY-MM-DD HH:MM:SS
    end_time: str
    run_status: str
    file_template: str
    binning: int


@dataclass
class Position:
    position_x: float
    position_y: float
    position_z: float


@dataclass
class DataCollectionGroup:
    visit: str # required
    experiment_type: str
    sample_id: int
    sample_barcode: str
