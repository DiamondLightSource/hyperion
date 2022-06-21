from ophyd import Device, EpicsMotor
from ophyd import Component as Cpt

class Scintillator(Device):
	y: EpicsMotor = Cpt(EpicsMotor, '-MO-SCIN-01:Y')
	z: EpicsMotor = Cpt(EpicsMotor, '-MO-SCIN-01:Z')


