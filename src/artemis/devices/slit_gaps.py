from ophyd import Component, Device, EpicsSignal


class SlitGaps(Device):

    xgap: EpicsSignal = Component(EpicsSignal, "BL03I-AL-SLITS-04:XGAP")
    ygap: EpicsSignal = Component(EpicsSignal, "BL03I-AL-SLITS-04:YGAP")
