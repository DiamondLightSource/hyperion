from ophyd import Component, Device, EpicsMotor


class Undulator(Device):
    gap: EpicsMotor = Component(EpicsMotor, "BLGAPMTR")
