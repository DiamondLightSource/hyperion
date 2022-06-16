from ophyd import Component, Device, EpicsMotor

class Aperture(Device):
	x: EpicsMotor = Component(EpicsMotor, "-MO-MAPT-01:X")
	y: EpicsMotor = Component(EpicsMotor, "-MO-MAPT-01:Y")
	z: EpicsMotor = Component(EpicsMotor, "-MO-MAPT-01:Z")
