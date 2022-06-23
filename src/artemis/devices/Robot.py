from ophyd import Device, EpicsMotor, EpicsSignalRO
from ophyd import Component as Cpt


class BART(Device):
	GonioPinSensor: EpicsSignalRO = Cpt(EpicsSignalRO, '-MO-ROBOT-01:PIN_MOUNTED')

