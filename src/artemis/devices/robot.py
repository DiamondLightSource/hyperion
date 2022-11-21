from ophyd import Component as Cpt
from ophyd import Device, EpicsSignalRO


class BART(Device):
    GonioPinSensor: EpicsSignalRO = Cpt(EpicsSignalRO, "-MO-ROBOT-01:PIN_MOUNTED")
