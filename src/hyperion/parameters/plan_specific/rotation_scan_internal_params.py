from __future__ import annotations

from dodal.devices.detector import DetectorParams, TriggerMode
from dodal.devices.motors import XYZLimitBundle
from dodal.devices.zebra import RotationDirection
from dodal.parameters.experiment_parameter_base import AbstractExperimentParameterBase
from pydantic import BaseModel, validator
from scanspec.core import Path as ScanPath
from scanspec.specs import Line

from hyperion.external_interaction.ispyb.ispyb_dataclass import (
    RotationIspybParams,
)
from hyperion.parameters.external_parameters import ExternalParameters
from hyperion.parameters.internal_parameters import (
    InternalParameters,
)


class RotationScanParams(BaseModel, AbstractExperimentParameterBase):
    """
    Holder class for the parameters of a rotation data collection.
    """

    rotation_axis: str = "omega"
    rotation_angle: float = 360.0
    image_width_deg: float = 0.1
    omega_start_deg: float = 0.0
    phi_start: float | None = None
    chi_start: float | None = None
    kappa_start: float | None = None
    x: float | None = None
    y: float | None = None
    z: float | None = None
    rotation_direction: RotationDirection = RotationDirection.NEGATIVE
    shutter_opening_time_s: float = 0.6

    @validator("rotation_direction", pre=True)
    def _parse_direction(cls, rotation_direction: str | int | RotationDirection):
        if isinstance(rotation_direction, str):
            return RotationDirection[rotation_direction]
        else:
            return RotationDirection(rotation_direction)

    def xyz_are_valid(self, limits: XYZLimitBundle) -> bool:
        """
        Validates scan location in x, y, and z

        :param limits: The motor limits against which to validate
                       the parameters
        :return: True if the scan is valid
        """
        if not limits.x.is_within(self.x):
            return False
        if not limits.y.is_within(self.y):
            return False
        if not limits.z.is_within(self.z):
            return False
        return True

    def get_num_images(self):
        return int(self.rotation_angle / self.image_width_deg)


class RotationInternalParameters(InternalParameters):
    experiment_params: RotationScanParams
    ispyb_params: RotationIspybParams

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def from_external(cls, external: ExternalParameters):
        (
            data_params,
            expt_params,
            zocalo_environment,
            beamline,
            insertion_prefix,
            experiment_type,
        ) = cls._common_from_external(external)
        if (
            expt_params["rotation_axis"] == "omega"
            and expt_params.get("rotation_increment_deg") is not None
        ):
            expt_params["omega_increment_deg"] = expt_params["rotation_increment_deg"]
        else:
            expt_params["omega_increment_deg"] = 0
        expt_params["num_triggers"] = 1
        experiment_params = RotationScanParams(
            **data_params,
            **expt_params,
        )
        expt_params["num_images_per_trigger"] = experiment_params.get_num_images()
        expt_params["trigger_mode"] = TriggerMode.SET_FRAMES
        expt_params["prefix"] = external.data_parameters.filename_prefix

        return cls(
            params_version=external.parameter_version,
            zocalo_environment=zocalo_environment,
            beamline=beamline,
            insertion_prefix=insertion_prefix,
            experiment_type=experiment_type,
            ispyb_params=RotationIspybParams(**data_params, **expt_params),
            detector_params=DetectorParams(**data_params, **expt_params),
            experiment_params=experiment_params,
        )

    def get_scan_points(self):
        scan_spec = Line(
            axis="omega",
            start=self.experiment_params.omega_start_deg,
            stop=(
                self.experiment_params.rotation_angle
                + self.experiment_params.omega_start_deg
            ),
            num=self.experiment_params.get_num_images(),
        )
        scan_path = ScanPath(scan_spec.calculate())
        return scan_path.consume().midpoints

    def get_data_shape(self) -> tuple[int, int, int]:
        size = self.detector_params.detector_size_constants.det_size_pixels
        return (self.experiment_params.get_num_images(), size.width, size.height)
