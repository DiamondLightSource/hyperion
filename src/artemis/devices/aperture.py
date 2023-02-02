from enum import Enum

from ophyd import Component, Device, EpicsMotor


class ApertureSize(Enum):
    # TODO load MAPT:Y positions from file
    SMALL = 1
    MEDIUM = 2
    LARGE = 3


class Aperture(Device):
    x: EpicsMotor = Component(EpicsMotor, "X")
    y: EpicsMotor = Component(EpicsMotor, "Y")
    z: EpicsMotor = Component(EpicsMotor, "Z")

    def set_size(self, size: ApertureSize):
        self.y.set(size)
