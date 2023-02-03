import copy
from dataclasses import dataclass, field
from os import environ

from dataclasses_json import dataclass_json
from dodal.devices.eiger import DETECTOR_PARAM_DEFAULTS, DetectorParams
from dodal.devices.fast_grid_scan import GridScanParams

from artemis.external_interaction.ispyb.ispyb_dataclass import IspybParams
from artemis.utils import Point3D

SIM_BEAMLINE = "BL03S"
SIM_INSERTION_PREFIX = "SR03S"
ISPYB_PLAN_NAME = "ispyb_readings"
SIM_ZOCALO_ENV = "devrmq"
SIM_ISPYB_CONFIG = "src/artemis/external_interaction/unit_tests/test_config.cfg"


def default_field(obj):
    return field(default_factory=lambda: copy.deepcopy(obj))


@dataclass
class BeamlinePrefixes:
    beamline_prefix: str
    insertion_prefix: str


def get_beamline_prefixes():
    beamline = environ.get("BEAMLINE")
    if beamline is None:
        return BeamlinePrefixes(SIM_BEAMLINE, SIM_INSERTION_PREFIX)
    if beamline == "i03":
        return BeamlinePrefixes("BL03I", "SR03I")


@dataclass_json
@dataclass
class FullParameters:
    zocalo_environment: str = SIM_ZOCALO_ENV
    beamline: str = SIM_BEAMLINE
    insertion_prefix: str = SIM_INSERTION_PREFIX
    grid_scan_params: GridScanParams = default_field(
        GridScanParams(
            x_steps=4,
            y_steps=200,
            z_steps=61,
            x_step_size=0.1,
            y_step_size=0.1,
            z_step_size=0.1,
            dwell_time=0.2,
            x_start=0.0,
            y1_start=0.0,
            y2_start=0.0,
            z1_start=0.0,
            z2_start=0.0,
        )
    )
    detector_params: DetectorParams = default_field(
        DetectorParams(**DETECTOR_PARAM_DEFAULTS)
    )
    ispyb_params: IspybParams = default_field(
        IspybParams(
            sample_id=None,
            sample_barcode=None,
            visit_path="",
            pixels_per_micron_x=0.0,
            pixels_per_micron_y=0.0,
            upper_left=Point3D(
                x=0, y=0, z=0
            ),  # gets stored as 2x2D coords - (x, y) and (x, z). Values in pixels
            position=Point3D(x=0, y=0, z=0),
            xtal_snapshots_omega_start=["test_1_y", "test_2_y", "test_3_y"],
            xtal_snapshots_omega_end=["test_1_z", "test_2_z", "test_3_z"],
            transmission=1.0,
            flux=10.0,
            wavelength=0.01,
            beam_size_x=0.1,
            beam_size_y=0.1,
            focal_spot_size_x=0.0,
            focal_spot_size_y=0.0,
            comment="Descriptive comment.",
            resolution=1,
            undulator_gap=1.0,
            synchrotron_mode=None,
            slit_gap_size_x=0.1,
            slit_gap_size_y=0.1,
        )
    )
