from dataclasses import dataclass
from typing import Optional

from dataclasses_json import DataClassJsonMixin

from artemis.devices.motors import XYZLimitBundle


@dataclass
class RotationScanParams(DataClassJsonMixin):
    """
    Holder class for the parameters of a rotation data collection.
    """

    rotation_axis: str = "omega"
    rotation_angle: float = 360.0
    omega_start: float = 0.0
    phi_start: float = 0.0
    chi_start: Optional[float] = None
    kappa_start: Optional[float] = None
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

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
