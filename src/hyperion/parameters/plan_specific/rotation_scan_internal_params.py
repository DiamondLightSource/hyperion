from __future__ import annotations

from dodal.devices.detector import DetectorParams
from dodal.devices.motors import XYZLimitBundle
from dodal.devices.zebra import RotationDirection
from dodal.parameters.experiment_parameter_base import AbstractExperimentParameterBase
from pydantic import BaseModel, validator
from scanspec.core import Path as ScanPath
from scanspec.specs import Line

from hyperion.external_interaction.ispyb.ispyb_dataclass import (
    GRIDSCAN_ISPYB_PARAM_DEFAULTS,
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
    image_width: float = 0.1
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
    def _parse_direction(cls, rotation_direction: str | int):
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
        return int(self.rotation_angle / self.image_width)


class RotationInternalParameters(InternalParameters):
    experiment_params: RotationScanParams
    ispyb_params: RotationIspybParams

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def from_external(cls, external: ExternalParameters):
        return cls(
            params_version=external.parameter_version,
            hyperion_params=HyperionParameters.from_external(external),
            ispyb_params=RotationIspybParams.from_external(external),
            experiment_params=RotationScanParams(
                **external.data_parameters.dict(),
                **external.experiment_parameters.dict(),
            ),
        )

    # @validator("hyperion_params", pre=True)
    # def _preprocess_hyperion_params(
    #     cls, all_params: dict[str, Any], values: dict[str, Any]
    # ):
    #     experiment_params: RotationScanParams = values["experiment_params"]
    #     all_params["num_images"] = experiment_params.get_num_images()
    #     all_params["position"] = np.array(all_params["position"])
    #     if (
    #         all_params["rotation_axis"] == "omega"
    #         and all_params.get("rotation_increment") is not None
    #     ):
    #         all_params["omega_increment_deg"] = all_params["rotation_increment"]
    #     else:
    #         all_params["omega_increment_deg"] = 0
    #     all_params["num_triggers"] = 1
    #     all_params["num_images_per_trigger"] = all_params["num_images"]
    #     return RotationHyperionParameters(
    #         **extract_hyperion_params_from_flat_dict(
    #             all_params, cls._hyperion_param_key_definitions()
    #         )
    #     )

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
