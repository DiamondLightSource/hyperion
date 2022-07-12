from ophyd import Device, EpicsSignal,EpicsSignalRO,  EpicsMotor
from ophyd import Component as Cpt


class Attenuators(Device):
	target_transmission: EpicsSignal = Cpt(EpicsSignal, '-EA-ATTN-01:TRANS_PERCENT')
	possible_transmission: EpicsSignalRO = Cpt(EpicsSignalRO, '-EA-ATTN-01:CONV_TRANS_RBV')
	apply_transmission: EpicsSignal = Cpt(EpicsSignal, '-EA-ATTN-01:FANOUT')
	applied_transmission: EpicsSignalRO = Cpt(EpicsSignalRO, '-EA-ATTN-01:LAST_APPLIED_TRANS')
	









