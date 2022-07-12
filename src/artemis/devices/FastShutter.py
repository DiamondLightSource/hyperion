from ophyd import Device, EpicsSignal,EpicsSignalRO, EpicsMotor
from ophyd import Component as Cpt

class FastShutter(Device):
	mode: EpicsSignal = Cpt(EpicsSignal, '-EA-SHTR-01:CTRL1')
	control: EpicsSignal = Cpt(EpicsSignal, '-EA-SHTR-01:CTRL2')
	status: EpicsSignalRO = Cpt(EpicsSignalRO, '-EA-ZEBRA-01:OUT2_TTL:STA')


