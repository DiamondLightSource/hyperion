from dataclasses import dataclass, field

from ophyd import EpicsMotor
from ophyd.device import Component
from ophyd.epics_motor import MotorBundle


class GridScanLimit:
    """
    Represents motor limit(s)
    """

    def __init__(self, motor: EpicsMotor):
        motor.wait_for_connection()
        self.low = motor.low_limit_travel.get()
        self.high = motor.high_limit_travel.get()

    def is_within(self, position: float) -> bool:
        """Checks position against limits

        :param position: The position to check
        :return: True if position is within the limits
        """
        return self.low <= position <= self.high


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

    x: EpicsMotor = Component(EpicsMotor, ":X")
    y: EpicsMotor = Component(EpicsMotor, ":Y")
    z: EpicsMotor = Component(EpicsMotor, ":Z")

    def get_limits(self) -> GridScanLimitBundle:
        return GridScanLimitBundle(
            GridScanLimit(self.x),
            GridScanLimit(self.y),
            GridScanLimit(self.z),
        )
