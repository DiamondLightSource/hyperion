from dataclasses import dataclass

from ophyd import EpicsMotor


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
