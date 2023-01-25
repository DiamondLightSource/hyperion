import copy
import json
from dataclasses import dataclass, field
from os import environ
from pathlib import Path
from typing import NamedTuple, Optional, Union

import jsonschema
from dataclasses_json import DataClassJsonMixin

from artemis.parameters.constants import (
    EXPERIMENT_DICT,
    EXPERIMENT_NAMES,
    EXPERIMENT_TYPES,
    PARAMETER_VERSION,
    SIM_BEAMLINE,
    SIM_INSERTION_PREFIX,
    SIM_ZOCALO_ENV,
)
from artemis.utils import Point3D


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


def default_field(obj):
    return field(default_factory=lambda: copy.deepcopy(obj))


class WrongExperimentParameterSpecification(Exception):
    pass


@dataclass
class ExternalDetectorParameters(DataClassJsonMixin):
    current_energy: Optional[int] = None
    exposure_time: Optional[float] = None
    directory: str = "/tmp"
    prefix: str = "file_name"
    run_number: int = 0
    detector_distance: Optional[float] = None
    omega_start: Optional[float] = None
    omega_increment: Optional[float] = None
    num_images: Optional[int] = None
    use_roi_mode: bool = False
    det_dist_to_beam_converter_path: str = (
        "src/artemis/devices/unit_tests/test_lookup_table.txt"
    )
    detector_size_constants: Optional[str] = "EIGER2_X_16M"


@dataclass
class ExternalISPyBParameters(DataClassJsonMixin):
    sample_id: Optional[int] = None
    sample_barcode: Optional[str] = None
    visit_path: str = ""
    pixels_per_micron_x: Optional[float] = None
    pixels_per_micron_y: Optional[float] = None
    # gets stored as 2x2D coords - (x, y) and (x, z). Values in pixels
    upper_left: NamedTuple = Point3D(x=0, y=0, z=0)
    position: NamedTuple = Point3D(x=0, y=0, z=0)
    xtal_snapshots_omega_start: list[str] = default_field(
        ["test_1_y", "test_2_y", "test_3_y"]
    )
    xtal_snapshots_omega_end: list[str] = default_field(
        ["test_1_y", "test_2_y", "test_3_y"]
    )
    transmission: Optional[float] = None
    flux: Optional[float] = None
    wavelength: Optional[float] = None
    beam_size_x: Optional[float] = None
    beam_size_y: Optional[float] = None
    focal_spot_size_x: Optional[float] = None
    focal_spot_size_y: Optional[float] = None
    comment: str = "Descriptive comment."
    resolution: Optional[float] = None
    undulator_gap: Optional[float] = None
    synchrotron_mode: Optional[str] = None
    slit_gap_size_x: Optional[float] = None
    slit_gap_size_y: Optional[float] = None


@dataclass
class ExternalGridScanParameters(DataClassJsonMixin):
    x_steps: int = 4
    y_steps: int = 200
    z_steps: int = 61
    x_step_size: float = 0.1
    y_step_size: float = 0.1
    z_step_size: float = 0.1
    dwell_time: float = 0.2
    x_start: float = 0.0
    y1_start: float = 0.0
    y2_start: float = 0.0
    z1_start: float = 0.0
    z2_start: float = 0.0


@dataclass
class ExternalRotationScanParameters(DataClassJsonMixin):
    x_steps: int = 4
    y_steps: int = 200
    z_steps: int = 61
    x_step_size: float = 0.1
    y_step_size: float = 0.1
    z_step_size: float = 0.1
    dwell_time: float = 0.2
    x_start: float = 0.0
    y1_start: float = 0.0
    y2_start: float = 0.0
    z1_start: float = 0.0
    z2_start: float = 0.0


@dataclass
class ExternalArtemisParameters(DataClassJsonMixin):
    zocalo_environment: str = SIM_ZOCALO_ENV
    beamline: str = SIM_BEAMLINE
    insertion_prefix: str = SIM_INSERTION_PREFIX
    experiment_type: str = EXPERIMENT_NAMES[0]
    detector_params: ExternalDetectorParameters = default_field(
        ExternalDetectorParameters()
    )
    ispyb_params: ExternalISPyBParameters = default_field(ExternalISPyBParameters())


EXTERNAL_EXPERIMENT_PARAM_TYPES = Union[
    ExternalGridScanParameters, ExternalRotationScanParameters
]


class RawParameters:
    artemis_params: ExternalArtemisParameters
    experiment_params: EXTERNAL_EXPERIMENT_PARAM_TYPES

    def __init__(
        self,
        artemis_parameters: ExternalArtemisParameters = ExternalArtemisParameters(),
        experiment_parameters: EXTERNAL_EXPERIMENT_PARAM_TYPES = ExternalGridScanParameters(),
    ) -> None:
        self.artemis_params = copy.deepcopy(artemis_parameters)
        self.experiment_params = copy.deepcopy(experiment_parameters)

    def __eq__(self, other) -> bool:
        if not isinstance(other, RawParameters):
            return NotImplemented
        if self.artemis_params != other.artemis_params:
            return False
        if self.experiment_params != other.experiment_params:
            return False
        return True

    def to_dict(self) -> dict[str, dict]:
        return {
            "params_version": PARAMETER_VERSION,
            "artemis_params": self.artemis_params.to_dict(),
            "experiment_params": self.experiment_params.to_dict(),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, dict_params: dict[str, dict]):
        with open(
            "src/artemis/parameters/schemas/full_external_parameters_schema.json", "r"
        ) as f:
            full_schema = json.load(f)

        path = Path("src/artemis/parameters/schemas/").absolute()
        resolver = jsonschema.validators.RefResolver(
            base_uri=f"{path.as_uri()}/",
            referrer=True,
        )
        # TODO improve failed validation error messages
        jsonschema.validate(dict_params, full_schema, resolver=resolver)
        experiment_type: EXPERIMENT_TYPES = EXPERIMENT_DICT.get(
            dict_params["artemis_params"]["experiment_type"]
        )
        try:
            assert experiment_type is not None
            experiment_params = experiment_type.from_dict(
                dict_params["experiment_params"]
            )
        except Exception:
            raise WrongExperimentParameterSpecification(
                "Either the experiment type parameter does not match a known experiment"
                "type, or the experiment parameters were not correct."
            )
        return cls(
            ExternalArtemisParameters.from_dict(dict_params["artemis_params"]),
            experiment_params,
        )

    @classmethod
    def from_json(cls, json_params: str):
        dict_params = json.loads(json_params)
        return cls.from_dict(dict_params)

    @classmethod
    def from_file(cls, json_filename: str):
        with open(json_filename) as f:
            return cls.from_json(f.read())
