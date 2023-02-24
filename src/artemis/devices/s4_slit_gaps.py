from ophyd import Component, Device, EpicsMotor


class S4SlitGaps(Device):
    """Note that the S4 slits have a different PV fromat to other beamline slits"""

    xgap: EpicsMotor = Component(EpicsMotor, "XGAP")
    ygap: EpicsMotor = Component(EpicsMotor, "YGAP")
