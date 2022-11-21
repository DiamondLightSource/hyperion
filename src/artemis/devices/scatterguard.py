from ophyd import Component as Cpt
from ophyd import Device, EpicsMotor


class Scatterguard(Device):
    x: EpicsMotor = Cpt(EpicsMotor, "-MO-SCAT-01:X")
    y: EpicsMotor = Cpt(EpicsMotor, "-MO-SCAT-01:Y")
