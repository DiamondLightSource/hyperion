from ophyd import Component as Cpt
from ophyd import Device, EpicsMotor


class BeamStop(Device):
    x: EpicsMotor = Cpt(EpicsMotor, "-MO-BS-01:X")
    y: EpicsMotor = Cpt(EpicsMotor, "-MO-BS-01:Y")
    z: EpicsMotor = Cpt(EpicsMotor, "-MO-BS-01:Z")
