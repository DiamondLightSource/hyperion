from ophyd import Device, EpicsSignal, EpicsMotor
from ophyd import Component as Cpt

class FluorescenceDetector(Device):
	
	pos: EpicsSignal = Cpt(EpicsSignal, '-EA-FLU-01:CTRL')


