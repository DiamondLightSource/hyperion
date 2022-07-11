from ophyd import Component, Device, EpicsSignal


class SlitGaps(Device):

    xgap: EpicsSignal = Component(EpicsSignal, "XGAP")
    ygap: EpicsSignal = Component(EpicsSignal, "YGAP")
