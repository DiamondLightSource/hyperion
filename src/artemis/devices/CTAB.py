from ophyd import Device, EpicsMotor
from ophyd import Component as Cpt

class CTAB(Device):
	'''CTAB is the collimation table. It is interlocked with the detector for safe movement''' 

	inboard_y: EpicsMotor = Cpt(EpicsMotor, '-MO-TABLE-01:INBOARDY')
	outboard_y: EpicsMotor = Cpt(EpicsMotor, '-MO-TABLE-01:OUTBOARDY')
	upstream_y: EpicsMotor = Cpt(EpicsMotor, '-MO-TABLE-01:UPSTREAMY')
	combined_downstream_y: EpicsMotor = Cpt(EpicsMotor, '-MO-TABLE-01:DOWNSTREAMY')
	combined_all_y: EpicsMotor = Cpt(EpicsMotor, '-MO-TABLE-01:Y')

	downstream_x: EpicsMotor = Cpt(EpicsMotor, '-MO-TABLE-01:DOWNSTREAMX')
	upstream_x: EpicsMotor = Cpt(EpicsMotor, '-MO-TABLE-01:UPSTREAMX')
	combined_all_x: EpicsMotor = Cpt(EpicsMotor, '-MO-TABLE-01:X')
	
	pitch: EpicsMotor = Cpt(EpicsMotor, '-MO-TABLE-01:PITCH')
	roll: EpicsMotor = Cpt(EpicsMotor, '-MO-TABLE-01:ROLL')
	yaw: EpicsMotor = Cpt(EpicsMotor, '-MO-TABLE-01:YAW')
