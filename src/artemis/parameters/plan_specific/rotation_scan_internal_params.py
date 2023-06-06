from __future__ import annotations

from typing import Any, Optional

import numpy as np
from dodal.devices.detector import DetectorParams
from dodal.devices.motors import XYZLimitBundle
from dodal.devices.zebra import RotationDirection
from dodal.parameters.experiment_parameter_base import AbstractExperimentParameterBase
from pydantic import BaseModel, validator

from artemis.external_interaction.ispyb.ispyb_dataclass import (
    GRIDSCAN_ISPYB_PARAM_DEFAULTS,
    GridscanIspybParams,
    IspybParams,
    RotationIspybParams,
)
from artemis.parameters.constants import (
    DEFAULT_EXPERIMENT_TYPE,
    DETECTOR_PARAM_DEFAULTS,
    SIM_BEAMLINE,
    SIM_INSERTION_PREFIX,
    SIM_ZOCALO_ENV,
)
from artemis.parameters.internal_parameters import (
    ArtemisParameters,
    InternalParameters,
    extract_artemis_params_from_flat_dict,
    extract_experiment_params_from_flat_dict,
)


class RotationArtemisParameters(ArtemisParameters):
    ispyb_params: IspybParams = RotationIspybParams(**GRIDSCAN_ISPYB_PARAM_DEFAULTS)

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            **DetectorParams.Config.json_encoders,
            **GridscanIspybParams.Config.json_encoders,
        }


class RotationScanParams(BaseModel, AbstractExperimentParameterBase):
    """
    Holder class for the parameters of a rotation data collection.
    """

    rotation_axis: str = "omega"
    rotation_angle: float = 360.0
    image_width: float = 0.1
    omega_start: float = 0.0
    phi_start: float = 0.0
    chi_start: Optional[float] = None
    kappa_start: Optional[float] = None
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    rotation_direction: RotationDirection = RotationDirection.NEGATIVE
    offset_deg: float = 1.0
    shutter_opening_time_s: float = 0.6

    @validator("rotation_direction", pre=True)
    def _parse_direction(cls, rotation_direction: str | int):
        return RotationDirection[rotation_direction]

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
    artemis_params: RotationArtemisParameters

    @staticmethod
    def _artemis_param_key_definitions() -> tuple[list[str], list[str], list[str]]:
        artemis_param_field_keys = [
            "zocalo_environment",
            "beamline",
            "insertion_prefix",
            "experiment_type",
        ]
        detector_field_keys = list(DetectorParams.__annotations__.keys())
        # not an annotation but specified as field encoder in DetectorParams:
        detector_field_keys.append("detector")
        ispyb_field_keys = list(IspybParams.__annotations__.keys()) + list(
            GridscanIspybParams.__annotations__.keys()
        )

        return artemis_param_field_keys, detector_field_keys, ispyb_field_keys

    @validator("experiment_params", pre=True)
    def _preprocess_experiment_params(
        cls,
        experiment_params: dict[str, Any],
    ):
        return RotationScanParams(
            **extract_experiment_params_from_flat_dict(
                RotationScanParams, experiment_params
            )
        )

    @validator("artemis_params", pre=True)
    def _preprocess_artemis_params(
        cls, all_params: dict[str, Any], values: dict[str, Any]
    ):
        experiment_params: RotationScanParams = values["experiment_params"]
        all_params["num_images"] = experiment_params.get_num_images()
        all_params["position"] = np.array(all_params["position"])
        if all_params["rotation_axis"] == "omega":
            all_params["omega_increment"] = all_params["rotation_increment"]
        else:
            all_params["omega_increment"] = 0
        all_params["num_triggers"] = 1
        all_params["num_images_per_trigger"] = all_params["num_images"]
        all_params["upper_left"] = np.array(all_params["upper_left"])
        return ArtemisParameters(
            **extract_artemis_params_from_flat_dict(
                all_params, cls._artemis_param_key_definitions()
            )
        )
