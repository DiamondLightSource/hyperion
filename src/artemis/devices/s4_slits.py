from ophyd import Component, Device, EpicsMotor


class S4Slits(Device):

    xgap: EpicsMotor = Component(EpicsMotor, "XGAP")
    ygap: EpicsMotor = Component(EpicsMotor, "YGAP")
    x: EpicsMotor = Component(EpicsMotor, "X")
    y: EpicsMotor = Component(EpicsMotor, "Y")
