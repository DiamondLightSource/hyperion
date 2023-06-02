from __future__ import annotations

from typing import Any

import numpy as np
from dodal.devices.motors import XYZLimitBundle
from dodal.devices.zebra import RotationDirection
from dodal.parameters.experiment_parameter_base import AbstractExperimentParameterBase
from pydantic import BaseModel, validator

from artemis.parameters.internal_parameters import (
    ArtemisParameters,
    InternalParameters,
    extract_artemis_params_from_flat_dict,
    extract_experiment_params_from_flat_dict,
)


class RotationScanParams(BaseModel, AbstractExperimentParameterBase):
    """
    Holder class for the parameters of a rotation data collection.
    """

    rotation_axis: str = "omega"
    rotation_angle: float = 360.0
    image_width: float = 0.1
    omega_start: float = 0.0
    phi_start: float = 0.0
    chi_start: float | None = None
    kappa_start: float | None = None
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    rotation_direction: RotationDirection = RotationDirection.NEGATIVE
    offset_deg: float = 1.0
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
    artemis_params: ArtemisParameters

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
        return ArtemisParameters(**extract_artemis_params_from_flat_dict(all_params))
