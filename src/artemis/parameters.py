import copy
from dataclasses import dataclass, field
from os import environ
from typing import Any, Tuple, cast

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
I03_BEAMLINE_PARAMETER_PATH = (
    "/dls_sw/i03/software/daq_configuration/domain/beamlineParameters"
)
BEAMLINE_PARAMETER_KEYWORDS = ["FB", "FULL", "deadtime"]


def default_field(obj):
    return field(default_factory=lambda: copy.deepcopy(obj))


class GDABeamlineParameters:
    params: dict[str, Any]

    def __repr__(self) -> str:
        return repr(self.params)

    def __getitem__(self, item: str):
        return self.params[item]

    @classmethod
    def from_file(cls, path: str):
        ob = cls()
        with open(path) as f:
            config_lines = f.readlines()
        config_lines_nocomments = [line.split("#", 1)[0] for line in config_lines]
        config_lines_sep_key_and_value = [
            line.translate(str.maketrans("", "", " \n\t\r")).split("=")
            for line in config_lines_nocomments
        ]
        config_pairs: list[tuple[str, Any]] = [
            cast(Tuple[str, Any], param)
            for param in config_lines_sep_key_and_value
            if len(param) == 2
        ]
        for i, (param, value) in enumerate(config_pairs):
            if value == "Yes":
                config_pairs[i] = (config_pairs[i][0], True)
            elif value == "No":
                config_pairs[i] = (config_pairs[i][0], False)
            elif value in BEAMLINE_PARAMETER_KEYWORDS:
                pass
            else:
                config_pairs[i] = (config_pairs[i][0], float(config_pairs[i][1]))
        ob.params = dict(config_pairs)
        return ob


@dataclass
class AperturePositions:
    """Holds the tuple (miniap_x, miniap_y, miniap_z, scatterguard_x, scatterguard_y)
    representing the motor positions needed to select a particular aperture size.
    """

    LARGE: tuple[float, float, float, float, float]
    MEDIUM: tuple[float, float, float, float, float]
    SMALL: tuple[float, float, float, float, float]
    ROBOT_LOAD: tuple[float, float, float, float, float]

    @classmethod
    def from_gda_beamline_params(cls, params: GDABeamlineParameters):
        return cls(
            LARGE=(
                params["miniap_x_LARGE_APERTURE"],
                params["miniap_y_LARGE_APERTURE"],
                params["miniap_z_LARGE_APERTURE"],
                params["sg_x_LARGE_APERTURE"],
                params["sg_y_LARGE_APERTURE"],
            ),
            MEDIUM=(
                params["miniap_x_MEDIUM_APERTURE"],
                params["miniap_y_MEDIUM_APERTURE"],
                params["miniap_z_MEDIUM_APERTURE"],
                params["sg_x_MEDIUM_APERTURE"],
                params["sg_y_MEDIUM_APERTURE"],
            ),
            SMALL=(
                params["miniap_x_SMALL_APERTURE"],
                params["miniap_y_SMALL_APERTURE"],
                params["miniap_z_SMALL_APERTURE"],
                params["sg_x_SMALL_APERTURE"],
                params["sg_y_SMALL_APERTURE"],
            ),
            ROBOT_LOAD=(
                params["miniap_x_ROBOT_LOAD"],
                params["miniap_y_ROBOT_LOAD"],
                params["miniap_z_ROBOT_LOAD"],
                params["sg_x_ROBOT_LOAD"],
                params["sg_y_ROBOT_LOAD"],
            ),
        )


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
