from ophyd import Component as Cpt
from ophyd import Device, EpicsSignal


class FluorescenceDetector(Device):

    OUT = 0
    IN = 1

    pos: EpicsSignal = Cpt(EpicsSignal, "-EA-FLU-01:CTRL")
