from typing import Any

from dodal.devices.det_dist_to_beam_converter import DetectorDistanceToBeamXYConverter
from dodal.devices.detector import DetectorParams, TriggerMode
from dodal.devices.zebra import RotationDirection
from numpy import isin
from pydantic import (
    BaseModel,
    Extra,
    NonNegativeFloat,
    NonNegativeInt,
    StrictFloat,
    StrictInt,
    validator,
)
from semver import Version


class ParameterVersion(Version):
    @classmethod
    def _parse(cls, version):
        if isinstance(version, cls):
            return version
        return cls.parse(version)

    @classmethod
    def __get_validators__(cls):
        """Return a list of validator methods for pydantic models."""
        yield cls._parse

    @classmethod
    def __modify_schema__(cls, field_schema):
        """Inject/mutate the pydantic field schema in-place."""
        field_schema.update(examples=["1.0.2", "2.15.3-alpha", "21.3.15-beta+12345"])


EXTERNAL_PARAMETERS_VERSION = ParameterVersion(5, 0, 0)


class ExternalExperimentParameters(BaseModel):
    chi_start_deg: StrictFloat | None = None
    det_dist_to_beam_converter_path: str | None = None
    detector_distance_mm: NonNegativeFloat | None = None
    detector: str | None = None
    dwell_time_ms: StrictInt | None = None
    energy_ev: NonNegativeFloat | None = None
    exposure_time_s: NonNegativeFloat | None = None
    image_width_deg: StrictFloat | None = None
    kappa_start_deg: StrictFloat | None = None
    num_images_per_trigger: int | None = None
    num_triggers: int | None = None
    omega_increment_deg: float | None = None
    omega_start_deg: float | None = None
    phi_start_deg: StrictFloat | None = None
    rotation_axis: str | None = None
    rotation_direction: RotationDirection | None = None
    rotation_increment_deg: float | None = None
    scan_width_deg: StrictFloat | None = None
    shutter_opening_time_s: float | None = None
    use_roi_mode: bool | None = None
    trigger_mode: TriggerMode | None = None
    x_steps: NonNegativeInt | None = None
    y_steps: NonNegativeInt | None = None
    z_steps: NonNegativeInt | None = None
    x_step_size_um: StrictFloat | None = None
    y_step_size_um: StrictFloat | None = None
    z_step_size_um: StrictFloat | None = None
    x_start_mm: StrictFloat | None = None
    y1_start_mm: StrictFloat | None = None
    y2_start_mm: StrictFloat | None = None
    z1_start_mm: StrictFloat | None = None
    z2_start_mm: StrictFloat | None = None
    x: StrictFloat | None = None
    y: StrictFloat | None = None
    z: StrictFloat | None = None

    # Not supplied, initialised by validators
    beam_xy_converter: DetectorDistanceToBeamXYConverter

    class Config:
        extra = Extra.forbid
        arbitrary_types_allowed = True
        json_encoders = {**DetectorParams.Config.json_encoders}

    @validator("trigger_mode", pre=True)
    def _parse_trigger_mode(cls, trigger_mode: str | int | TriggerMode):
        if trigger_mode is None:
            return None
        if isinstance(trigger_mode, TriggerMode):
            return trigger_mode
        if isinstance(trigger_mode, str):
            return TriggerMode[trigger_mode]
        else:
            return TriggerMode(trigger_mode)

    @validator("rotation_direction", pre=True)
    def _parse_direction(cls, rotation_direction: str | int | RotationDirection):
        if rotation_direction is None:
            return None
        if isinstance(rotation_direction, RotationDirection):
            return RotationDirection
        if isinstance(rotation_direction, str):
            return RotationDirection[rotation_direction]
        else:
            return RotationDirection(rotation_direction)

    @validator("beam_xy_converter", always=True, pre=True)
    def _parse_beam_xy_converter(
        cls,
        beam_xy_converter: DetectorDistanceToBeamXYConverter,
        values: dict[str, Any],
    ) -> DetectorDistanceToBeamXYConverter:
        return DetectorDistanceToBeamXYConverter(
            values["det_dist_to_beam_converter_path"]
        )


class ExternalDataParameters(BaseModel):
    beam_size_x_mm: float | None = None
    beam_size_y_mm: float | None = None
    beamline: str | None = None
    comment: str | None = None
    directory: str | None = None
    filename_prefix: str | None = None
    flux: float | None = None
    focal_spot_size_x_mm: float | None = None
    focal_spot_size_y_mm: float | None = None
    insertion_prefix: str | None = None
    microns_per_pixel_x: float | None = None
    microns_per_pixel_y: float | None = None
    resolution: float | None = None
    run_number: int | None = None
    sample_barcode: str | None = None
    sample_id: str | None = None
    slit_gap_size_x: float | None = None
    slit_gap_size_y: float | None = None
    synchrotron_mode: str | None = None
    transmission_fraction: float | None = None
    undulator_gap: float | None = None
    upper_left: list[str] | None = None
    visit_path: str | None = None
    xtal_snapshots_omega_end: list[str] | None = None
    xtal_snapshots_omega_start: list[str] | None = None
    zocalo_environment: str | None = None

    class Config:
        extra = Extra.forbid


class ExternalParameters(BaseModel):
    """Class for any and all parameters which could be supplied to Hyperion - for all
    experiment types. External parameters must only have the correct version, and no
    parameters which don't exist at all; InternalParameters classes are responsible for
    checking and reporting whether required values are supplied.

    ExternalParameters handles the conversions into Python datatypes from the raw JSON,
    e.g. turning lists into ndarrays, parsing enums, etc."""  # TODO revisit this - is is better to do this in internalparams which need to be serialised/deserialised anyway?

    parameter_version: ParameterVersion
    experiment_parameters: ExternalExperimentParameters
    data_parameters: ExternalDataParameters
    experiment_type: str | None = None

    class Config:
        use_enum_values = True
        arbitrary_types_allowed = True
        json_encoders = {
            ParameterVersion: lambda pv: str(pv),
        }

    @validator("parameter_version", pre=True)
    def _validate_version(
        cls, parameter_version: ParameterVersion | str, values: dict[str, Any]
    ) -> ParameterVersion:
        if isinstance(parameter_version, str):
            parameter_version = ParameterVersion.parse(parameter_version)
        assert (
            parameter_version.major == EXTERNAL_PARAMETERS_VERSION.major
        ), f"Parameters major version doesn't match - this version of Hyperion uses {EXTERNAL_PARAMETERS_VERSION.major}"
        assert parameter_version.minor <= EXTERNAL_PARAMETERS_VERSION.minor, (
            f"Parameters version too new - this version of Hyperion uses"
            f" {EXTERNAL_PARAMETERS_VERSION.major}.{EXTERNAL_PARAMETERS_VERSION.minor}.x"
        )
        return parameter_version
