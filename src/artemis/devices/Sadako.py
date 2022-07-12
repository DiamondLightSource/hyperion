from ophyd import Device, EpicsMotor, EpicsSignal, EpicsSignalRO
from ophyd import Component as Cpt


''' Various Ring associated PVs'''

class Ring(Device):
	topup: EpicsSignalRO = Cpt(EpicsSignalRO, 'SR-CS-FILL-01:COUNTDOWN')
	ring_current: EpicsSignalRO = Cpt(EpicsSignalRO, 'SR-DI-DCCT-01:SIGNAL')



''' Various Ring associated PVs'''
