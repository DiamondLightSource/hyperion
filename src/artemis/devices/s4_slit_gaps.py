from ophyd import Component, Device, EpicsSignal


class S4SlitGaps(Device):

    s4xgap: EpicsSignal = Component(EpicsSignal, "S4XGAP")
    s4ygap: EpicsSignal = Component(EpicsSignal, "S4YGAP")
