from ophyd import Device, EpicsSignal, EpicsSignalRO, EpicsMotor
from ophyd import Component as Cpt

class Cryo(Device):
	OUT=0
	IN=1
	course: EpicsSignal = Cpt(EpicsSignal, '-EA-CJET-01:COARSE:CTRL')
	fine: EpicsSignal = Cpt(EpicsSignal, '-EA-CJET-01:FINE:CTRL')
	temp: EpicsSignalRO = Cpt(EpicsSignalRO, '-EA-CSTRM-01:TEMP')
	backpress: EpicsSignalRO = Cpt(EpicsSignalRO, '-EA-CSTRM-01:BACKPRESS')
	
	

