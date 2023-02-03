import configparser
import copy
from dataclasses import dataclass, field
from os import environ
from typing import Any

from dataclasses_json import dataclass_json

from artemis.devices.eiger import DETECTOR_PARAM_DEFAULTS, DetectorParams
from artemis.devices.fast_grid_scan import GridScanParams
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
class ApertureSize:
    LARGE: tuple[float, float, float, float, float]
    MEDIUM: tuple[float, float, float, float, float]
    SMALL: tuple[float, float, float, float, float]


class GDABeamlineParameters:
    params: dict[str, Any]

    @classmethod
    def from_file(cls, path: str):
        ob = cls()
        parser = configparser.ConfigParser()
        parser.read_file(path)
        paramdict = {s: dict(parser.items(s)) for s in parser.sections()}
        ob.params = paramdict


# class ApertureSize(Enum):
#    # TODO load MAPT:Y positions from file
#
#    #    # 100 micron ap
#    #    miniap_x_LARGE_APERTURE = 2.385
#    #    miniap_y_LARGE_APERTURE = 40.984
#    #    miniap_z_LARGE_APERTURE = 15.8
#    #    sg_x_LARGE_APERTURE = 5.25
#    #    sg_y_LARGE_APERTURE = 4.43# 50 micron ap
#    #    miniap_x_MEDIUM_APERTURE = 2.379
#    #    miniap_y_MEDIUM_APERTURE = 44.971
#    #    miniap_z_MEDIUM_APERTURE = 15.8
#    #    sg_x_MEDIUM_APERTURE = 5.285
#    #    sg_y_MEDIUM_APERTURE = 0.46# 20 micron ap
#    #    miniap_x_SMALL_APERTURE = 2.426
#    #    miniap_y_SMALL_APERTURE = 48.977
#    #    miniap_z_SMALL_APERTURE = 15.8
#    #    sg_x_SMALL_APERTURE = 5.3375
#    #    sg_y_SMALL_APERTURE = -3.55
#
#    # (x, y, z, sg_x, sg_y)
#    SMALL = (1, 1, 1, 1, 1)
#    MEDIUM = (2, 2, 2, 2, 2)
#    LARGE = (3, 3, 3, 3, 3)


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
