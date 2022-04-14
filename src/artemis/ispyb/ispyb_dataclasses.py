from dataclasses import dataclass

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
    orientation # stored as String/Enum?
    snaked: bool


@dataclass
class DataCollection:
    visit: str
