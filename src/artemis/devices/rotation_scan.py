from typing import Optional

from artemis.devices.motors import XYZLimitBundle
from artemis.devices.parameters.base_experiment_device_parameters import (
    BaseExperimentDeviceParameters,
)


class RotationScanParams(BaseExperimentDeviceParameters):
    """
    Holder class for the parameters of a rotation data collection.
    """

    rotation_axis: str = "omega"
    rotation_angle: float = 360.0
    frame_width: float = 0.1
    omega_start: float = 0.0
    phi_start: float = 0.0
    chi_start: Optional[float] = None
    kappa_start: Optional[float] = None
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def get_num_images(self):
        return int(self.rotation_angle / self.frame_width)

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
