from ophyd import Device, EpicsMotor
from ophyd import Component as Cpt

class MiniAperture(Device):
	x: EpicsMotor = Cpt(EpicsMotor, '-MO-MAPT-01:X')
	y: EpicsMotor = Cpt(EpicsMotor, '-MO-MAPT-01:Y')
	z: EpicsMotor = Cpt(EpicsMotor, '-MO-MAPT-01:Z')



