from ophyd import Device, EpicsSignal, EpicsMotor
from ophyd import Component as Cpt

class Backlight(Device):
	
	pos: EpicsSignal = Cpt(EpicsSignal, '-EA-BL-01:CTRL')
