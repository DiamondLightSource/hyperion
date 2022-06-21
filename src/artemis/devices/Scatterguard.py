from ophyd import Device, EpicsMotor
from ophyd import Component as Cpt

class Scatterguard(Device):
	x: EpicsMotor = Cpt(EpicsMotor, '-MO-SCAT-01:X')
	y: EpicsMotor = Cpt(EpicsMotor, '-MO-SCAT-01:Y')



