from dataclasses import dataclass, field

from ophyd import EpicsMotor
from ophyd.device import Component
from ophyd.epics_motor import MotorBundle


@dataclass
class GridScanLimit:
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
class GridScanLimitBundle:
    """
    Holder for limits reflecting MX grid scan axes
    """

    x: GridScanLimit
    y: GridScanLimit
    z: GridScanLimit


class GridScanMotorBundle(MotorBundle):
    """
    Holder for motors reflecting grid scan axes
    """

    x: EpicsMotor = Component(EpicsMotor, "X")
    y: EpicsMotor = Component(EpicsMotor, "Y")
    z: EpicsMotor = Component(EpicsMotor, "Z")
    omega: EpicsMotor = Component(EpicsMotor, "OMEGA")

    def get_limits(self) -> GridScanLimitBundle:
        """Get the limits for the bundle.

        Note that these limits may not yet be valid until wait_for_connection is called on this MotorBundle.

        Returns:
            GridScanLimitBundle: The limits for the underlying motor.
        """
        return GridScanLimitBundle(
            GridScanLimit(self.x),
            GridScanLimit(self.y),
            GridScanLimit(self.z),
        )
