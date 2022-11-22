from ophyd import Component, Device, EpicsSignal


class Backlight(Device):
    OUT = 0
    IN = 1

    pos: EpicsSignal = Component(EpicsSignal, "CTRL")
