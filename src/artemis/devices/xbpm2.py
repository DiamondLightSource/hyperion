from ophyd import Component as Cpt
from ophyd import Device, EpicsSignalRO, Kind


class XBPM2(Device):
    intensity: EpicsSignalRO = Cpt(
        EpicsSignalRO, ":SumAll:MeanValue_RBV", kind=Kind.normal
    )
