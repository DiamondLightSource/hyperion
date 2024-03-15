from dataclasses import asdict, dataclass
from enum import Enum
from typing import Optional

from hyperion.external_interaction.ispyb.ispyb_dataclass import Orientation


class ExperimentType(Enum):
    # Enum values from ispyb column data type
    SAD = "SAD"  # at or slightly above the peak
    SAD_INVERSE_BEAM = "SAD - Inverse Beam"
    OSC = "OSC"  # "native" (in the absence of a heavy atom)
    COLLECT_MULTIWEDGE = (
        "Collect - Multiwedge"  # "poorly determined" ~ EDNA complex strategy???
    )
    MAD = "MAD"
    HELICAL = "Helical"
    MULTI_POSITIONAL = "Multi-positional"
    MESH = "Mesh"
    BURN = "Burn"
    MAD_INVERSE_BEAM = "MAD - Inverse Beam"
    CHARACTERIZATION = "Characterization"
    DEHYDRATION = "Dehydration"
    TOMO = "tomo"
    EXPERIMENT = "experiment"
    EM = "EM"
    PDF = "PDF"
    PDF_BRAGG = "PDF+Bragg"
    BRAGG = "Bragg"
    SINGLE_PARTICLE = "single particle"
    SERIAL_FIXED = "Serial Fixed"
    SERIAL_JET = "Serial Jet"
    STANDARD = "Standard"  # Routine structure determination experiment
    TIME_RESOLVED = "Time Resolved"  # Investigate the change of a system over time
    DLS_ANVIL_HP = "Diamond Anvil High Pressure"  # HP sample environment pressure cell
    CUSTOM = "Custom"  # Special or non-standard data collection
    XRF_MAP = "XRF map"
    ENERGY_SCAN = "Energy scan"
    XRF_SPECTRUM = "XRF spectrum"
    XRF_MAP_XAS = "XRF map xas"
    MESH_3D = "Mesh3D"
    SCREENING = "Screening"
    STILL = "Still"
    SSX_CHIP = "SSX-Chip"
    SSX_JET = "SSX-Jet"

    # Aliases for historic hyperion experiment type mapping
    ROTATION = "SAD"
    GRIDSCAN_2D = "mesh"
    GRIDSCAN_3D = "Mesh3D"


@dataclass()
class DataCollectionGroupInfo:
    visit_string: str
    experiment_type: str
    sample_id: Optional[str]
    sample_barcode: Optional[str] = None


@dataclass(kw_only=True)
class DataCollectionInfo:
    omega_start: Optional[float] = None
    data_collection_number: Optional[int] = None
    xtal_snapshot1: Optional[str] = None
    xtal_snapshot2: Optional[str] = None
    xtal_snapshot3: Optional[str] = None

    n_images: Optional[int] = None
    axis_range: Optional[float] = None
    axis_end: Optional[float] = None
    kappa_start: Optional[float] = None

    parent_id: Optional[int] = None
    visit_string: Optional[str] = None
    sample_id: Optional[str] = None
    detector_id: Optional[int] = None
    axis_start: Optional[float] = None
    focal_spot_size_at_samplex: Optional[float] = None
    focal_spot_size_at_sampley: Optional[float] = None
    slitgap_vertical: Optional[float] = None
    slitgap_horizontal: Optional[float] = None
    beamsize_at_samplex: Optional[float] = None
    beamsize_at_sampley: Optional[float] = None
    transmission: Optional[float] = None
    comments: Optional[str] = None
    detector_distance: Optional[float] = None
    exp_time: Optional[float] = None
    imgdir: Optional[str] = None
    file_template: Optional[str] = None
    imgprefix: Optional[str] = None
    imgsuffix: Optional[str] = None
    n_passes: Optional[int] = None
    overlap: Optional[int] = None
    flux: Optional[float] = None
    start_image_number: Optional[int] = None
    resolution: Optional[float] = None
    wavelength: Optional[float] = None
    xbeam: Optional[float] = None
    ybeam: Optional[float] = None
    synchrotron_mode: Optional[str] = None
    undulator_gap1: Optional[float] = None
    start_time: Optional[str] = None


@dataclass
class DataCollectionPositionInfo:
    pos_x: float
    pos_y: float
    pos_z: float


@dataclass
class DataCollectionGridInfo:
    dx_in_mm: float
    dy_in_mm: float
    steps_x: int
    steps_y: int
    microns_per_pixel_x: float
    microns_per_pixel_y: float
    snapshot_offset_x_pixel: int
    snapshot_offset_y_pixel: int
    orientation: Orientation
    snaked: bool

    def as_dict(self):
        d = asdict(self)
        d["orientation"] = self.orientation.value
        return d


@dataclass(kw_only=True)
class ScanDataInfo:
    data_collection_info: DataCollectionInfo
    data_collection_id: Optional[int] = None
    data_collection_position_info: Optional[DataCollectionPositionInfo] = None
    data_collection_grid_info: Optional[DataCollectionGridInfo] = None
