from ophyd import Device, EpicsMotor, EpicsSignal, EpicsSignalRO
from ophyd import Component as Cpt
from ophyd import Kind

class XBPM2(Device):
	intensity: EpicsSignalRO = Cpt(EpicsSignalRO, '-EA-XBPM-02:SumAll:MeanValue_RBV', kind=Kind.normal)




