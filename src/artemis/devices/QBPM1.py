from ophyd import Device, EpicsMotor, EpicsSignal, EpicsSignalRO
from ophyd import Component as Cpt
from ophyd import Kind

class QBPM1(Device):
	intensity: EpicsSignalRO = Cpt(EpicsSignalRO, '-DI-QBPM-01:INTEN', kind=Kind.normal)
	

