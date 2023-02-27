from ophyd import Component as Cpt
from ophyd import Device, EpicsMotor


class Scatterguard(Device):
    x: EpicsMotor = Cpt(EpicsMotor, "X")
    y: EpicsMotor = Cpt(EpicsMotor, "Y")
