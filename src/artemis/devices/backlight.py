from ophyd import Component, Device, EpicsSignal

"""Simple device to trigger the pneumatic in/out """


class Backlight(Device):
    OUT = 0
    IN = 1

    pos: EpicsSignal = Component(EpicsSignal, "-EA-BL-01:CTRL")
