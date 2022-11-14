from ophyd import Component as Cpt
from ophyd import Device, EpicsSignal, EpicsSignalRO


class Cryo(Device):

    course: EpicsSignal = Cpt(EpicsSignal, "-EA-CJET-01:COARSE:CTRL")
    fine: EpicsSignal = Cpt(EpicsSignal, "-EA-CJET-01:FINE:CTRL")
    temp: EpicsSignalRO = Cpt(EpicsSignalRO, "-EA-CSTRM-01:TEMP")
    backpress: EpicsSignalRO = Cpt(EpicsSignalRO, "-EA-CSTRM-01:BACKPRESS")
