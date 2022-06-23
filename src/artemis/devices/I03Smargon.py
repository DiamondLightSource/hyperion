
from ophyd import Device, EpicsMotor, EpicsSignal
from ophyd import Component as Cpt

class I03Smargon(Device):
	x: EpicsMotor = Cpt(EpicsMotor, '-MO-SGON-01:X')
	y: EpicsMotor = Cpt(EpicsMotor, '-MO-SGON-01:Y')
	z: EpicsMotor = Cpt(EpicsMotor, '-MO-SGON-01:Z')
	chi: EpicsMotor = Cpt(EpicsMotor, '-MO-SGON-01:CHI')
	phi: EpicsMotor = Cpt(EpicsMotor, '-MO-SGON-01:PHI')
	omega: EpicsMotor = Cpt(EpicsMotor, '-MO-SGON-01:OMEGA')

	stub_offset_set: EpicsSignal = Cpt(EpicsSignal, '-MO-SGON-01:SET_STUBS_TO_RL.PROC')

