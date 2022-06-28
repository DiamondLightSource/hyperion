from dataclasses import dataclass

from ophyd import EpicsMotor
from ophyd.device import Component
from ophyd.epics_motor import MotorBundle


@dataclass
class MotorLimitHelper:
    """
    Represents motor limit(s)
    """

    motor: EpicsMotor

    def is_within(self, position: float) -> bool:
        """Checks position against limits

        :param position: The position to check
        :return: True if position is within the limits
        """
        low = self.motor.low_limit_travel.get()
        high = self.motor.high_limit_travel.get()
        return low <= position <= high


@dataclass
class XYZLimitBundle:
    """
    Holder for limits reflecting an x, y, z bundle
    """

    x: MotorLimitHelper
    y: MotorLimitHelper
    z: MotorLimitHelper


class I03Smargon(MotorBundle):
    """
    Holder for motors reflecting grid scan axes
    """

    x: EpicsMotor = Component(EpicsMotor, "X")
    y: EpicsMotor = Component(EpicsMotor, "Y")
    z: EpicsMotor = Component(EpicsMotor, "Z")
    omega: EpicsMotor = Component(EpicsMotor, "OMEGA")

    def get_xyz_limits(self) -> XYZLimitBundle:
        """Get the limits for the x, y and z axes.

        Note that these limits may not yet be valid until wait_for_connection is called on this MotorBundle.

        Returns:
            XYZLimitBundle: The limits for the underlying motors.
        """
        return XYZLimitBundle(
            MotorLimitHelper(self.x),
            MotorLimitHelper(self.y),
            MotorLimitHelper(self.z),
        )
