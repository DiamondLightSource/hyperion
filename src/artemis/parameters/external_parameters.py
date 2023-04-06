from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Type, Union

import jsonschema
from dataclasses_json import DataClassJsonMixin
from jsonschema.exceptions import ValidationError

import artemis.experiment_plans.experiment_registry as registry
import artemis.log
from artemis.parameters.constants import (
    PARAMETER_VERSION,
    SIM_BEAMLINE,
    SIM_INSERTION_PREFIX,
    SIM_ZOCALO_ENV,
)


def default_field(obj):
    return field(default_factory=lambda: copy.deepcopy(obj))


class WrongExperimentParameterSpecification(Exception):
    pass


@dataclass
class ExternalDetectorParameters(DataClassJsonMixin):
    current_energy: int = 100
    directory: str = "/tmp"
    prefix: str = "file_name"
    run_number: int = 0
    use_roi_mode: bool = False
    det_dist_to_beam_converter_path: str = (
        "src/artemis/unit_tests/test_lookup_table.txt"
    )
    detector_size_constants: Optional[str] = "EIGER2_X_16M"


@dataclass
class ExternalISPyBParameters(DataClassJsonMixin):
    sample_id: Optional[int] = None
    sample_barcode: Optional[str] = None
    visit_path: str = ""
    microns_per_pixel_x: float = 0.0
    microns_per_pixel_y: float = 0.0
    # gets stored as 2x2D coords - (x, y) and (x, z). Values in pixels
    upper_left: Dict = default_field({"x": 0, "y": 0, "z": 0})
    position: Dict = default_field({"x": 0, "y": 0, "z": 0})
    xtal_snapshots_omega_start: list[str] = default_field(
        ["test_1_y", "test_2_y", "test_3_y"]
    )
    xtal_snapshots_omega_end: list[str] = default_field(
        ["test_1_y", "test_2_y", "test_3_y"]
    )
    transmission: float = 1.0
    flux: float = 10.0
    wavelength: float = 0.01
    beam_size_x: float = 0.1
    beam_size_y: float = 0.1
    focal_spot_size_x: float = 0.0
    focal_spot_size_y: float = 0.0
    comment: str = "Descriptive comment."
    resolution: float = 1
    undulator_gap: float = 1.0
    synchrotron_mode: Optional[str] = None
    slit_gap_size_x: float = 0.1
    slit_gap_size_y: float = 0.1


@dataclass
class ExternalGridScanParameters(DataClassJsonMixin):
    x_steps: int = 40
    y_steps: int = 20
    z_steps: int = 10
    x_step_size: float = 0.1
    y_step_size: float = 0.1
    z_step_size: float = 0.1
    dwell_time: float = 0.2
    x_start: float = 0.0
    y1_start: float = 0.0
    y2_start: float = 0.0
    z1_start: float = 0.0
    z2_start: float = 0.0
    exposure_time: float = 0.1
    detector_distance: float = 100.0
    omega_start: float = 0.0


@dataclass
class ExternalRotationScanParameters(DataClassJsonMixin):
    rotation_axis: str = "omega"
    rotation_angle: float = 180.0
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    omega_start: float = 0.0
    phi_start: float = 0.0
    chi_start: float = 0.0
    kappa_start: float = 0.0
    exposure_time: float = 0.1
    detector_distance: float = 100.0
    rotation_increment: float = 0.0


@dataclass
class ExternalArtemisParameters(DataClassJsonMixin):
    zocalo_environment: str = SIM_ZOCALO_ENV
    beamline: str = SIM_BEAMLINE
    insertion_prefix: str = SIM_INSERTION_PREFIX
    experiment_type: str = registry.EXPERIMENT_NAMES[0]
    detector_params: ExternalDetectorParameters = default_field(
        ExternalDetectorParameters()
    )
    ispyb_params: ExternalISPyBParameters = default_field(ExternalISPyBParameters())


EXTERNAL_EXPERIMENT_PARAM_TYPES = Union[
    ExternalGridScanParameters, ExternalRotationScanParameters
]
EXTERNAL_EXPERIMENT_PARAM_DICT: dict[str, Type] = {
    "fast_grid_scan": ExternalGridScanParameters,
    "rotation_scan": ExternalRotationScanParameters,
}


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
        try:
            jsonschema.validate(dict_params, full_schema, resolver=resolver)
        except ValidationError:
            artemis.log.LOGGER.error("Invalid json parameters")
            raise ValidationError("Invalid Json parameters")

        experiment_type = EXTERNAL_EXPERIMENT_PARAM_DICT.get(
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
