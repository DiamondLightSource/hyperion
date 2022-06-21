from ophyd import Device, EpicsMotor
from ophyd import Component as Cpt

class GonioLowerStages(Device):
	x: EpicsMotor = Cpt(EpicsMotor, '-MO-GONP-01:X')
	y: EpicsMotor = Cpt(EpicsMotor, '-MO-GONP-01:Y')
	z: EpicsMotor = Cpt(EpicsMotor, '-MO-GONP-01:Z')

