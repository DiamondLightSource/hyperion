from ophyd import Component as Cpt
from ophyd import Device, EpicsMotor, EpicsSignalRO


class CTAB(Device):
    """Basic collimantion table (CTAB) device for motion plus the motion disable signal
    when laser curtain triggered and hutch not locked.

    CTAB has 3 physical vertical motors, the jacks. 1 upstream and 2 downstream.
    The two downstream jacks are labelled as outboard (away from the ring) and
    inboard (towards the ring).
    Together these 3 jacks provide compound motion for vertical motion and pitch/roll.
    There are 2 physical horizontal motors 1 upstream, 1 downstream. These provide yaw.

    CTAB motion is disabled by an object being within the laser curtain area and can be
    overriden by use of the dead man's handle device or locking the hutch. The effect of
    these disabling systems is to cut power to the motors - signal for this is crate_power
    """

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
