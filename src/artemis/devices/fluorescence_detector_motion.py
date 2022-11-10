from ophyd import Component as Cpt
from ophyd import Device, EpicsSignal


class FluorescenceDetector(Device):

    pos: EpicsSignal = Cpt(EpicsSignal, "-EA-FLU-01:CTRL")
