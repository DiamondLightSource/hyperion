from ophyd import Component as Cpt
from ophyd import Device, EpicsMotor, EpicsSignalRO


class CTAB(Device):
    """Basic collimantion table (CTAB) device for motion plus the motion disable signal when laser curtain triggered and hutch not locked"""

    inboard_y: EpicsMotor = Cpt(EpicsMotor, "-MO-TABLE-01:INBOARDY")
    outboard_y: EpicsMotor = Cpt(EpicsMotor, "-MO-TABLE-01:OUTBOARDY")
    upstream_y: EpicsMotor = Cpt(EpicsMotor, "-MO-TABLE-01:UPSTREAMY")
    combined_downstream_y: EpicsMotor = Cpt(EpicsMotor, "-MO-TABLE-01:DOWNSTREAMY")
    combined_all_y: EpicsMotor = Cpt(EpicsMotor, "-MO-TABLE-01:Y")

    downstream_x: EpicsMotor = Cpt(EpicsMotor, "-MO-TABLE-01:DOWNSTREAMX")
    upstream_x: EpicsMotor = Cpt(EpicsMotor, "-MO-TABLE-01:UPSTREAMX")
    combined_all_x: EpicsMotor = Cpt(EpicsMotor, "-MO-TABLE-01:X")

    pitch: EpicsMotor = Cpt(EpicsMotor, "-MO-TABLE-01:PITCH")
    roll: EpicsMotor = Cpt(EpicsMotor, "-MO-TABLE-01:ROLL")
    yaw: EpicsMotor = Cpt(EpicsMotor, "-MO-TABLE-01:YAW")

    crate_power: EpicsSignalRO = Cpt(
        EpicsSignalRO, "-MO-PMAC-02:CRATE2_HEALTHY"
    )  # returns 0 if no power
