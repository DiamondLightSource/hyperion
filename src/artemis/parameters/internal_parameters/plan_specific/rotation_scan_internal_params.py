from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from dataclasses_json import DataClassJsonMixin
from dodal.devices.eiger import EigerTriggerNumber
from dodal.devices.motors import XYZLimitBundle
from dodal.parameters.experiment_parameter_base import AbstractExperimentParameterBase

from artemis.parameters.internal_parameters import InternalParameters


@dataclass
class RotationScanParams(DataClassJsonMixin, AbstractExperimentParameterBase):
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
    trigger_number: str = EigerTriggerNumber.MANY_TRIGGERS

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
    experiment_params_type = RotationScanParams

    def pre_sorting_translation(self, param_dict: dict[str, Any]):
        super().pre_sorting_translation(param_dict)
        if param_dict["rotation_angle"] == "omega":
            param_dict["omega_increment"] = param_dict["rotation_increment"]
        else:
            param_dict["omega_increment"] = 0
        param_dict["num_triggers"] = 1
        param_dict["num_images_per_trigger"] = param_dict["num_images"]
