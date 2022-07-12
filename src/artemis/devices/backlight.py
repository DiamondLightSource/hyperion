from ophyd import Device, EpicsSignal, EpicsMotor
from ophyd import Component as Cpt

class Backlight(Device):
	OUT=0
	IN=1
	pos: EpicsSignal = Cpt(EpicsSignal, '-EA-BL-01:CTRL')
