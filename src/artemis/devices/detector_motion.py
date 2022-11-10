from ophyd import Component as Cpt
from ophyd import Device, EpicsMotor, EpicsSignal, EpicsSignalRO

"""physical motion and interlocks for detector travel"""


class Det(Device):
    upstream_x: EpicsMotor = Cpt(EpicsMotor, "-MO-DET-01:UPSTREAMX")
    downstream_x: EpicsMotor = Cpt(EpicsMotor, "-MO-DET-01:DOWNSTREAMX")
    x: EpicsMotor = Cpt(EpicsMotor, "-MO-DET-01:X")
    y: EpicsMotor = Cpt(EpicsMotor, "-MO-DET-01:Y")
    z: EpicsMotor = Cpt(EpicsMotor, "-MO-DET-01:Z")
    yaw: EpicsMotor = Cpt(EpicsMotor, "-MO-DET-01:YAW")
    shutter: EpicsSignal = Cpt(
        EpicsSignal, "-MO-DET-01:SET_SHUTTER_STATE"
    )  # 0=closed, 1=open
    #   monitors
    shutter_closed_lim: EpicsSignalRO = Cpt(
        EpicsSignalRO, "-MO-DET-01:CLOSE_LIMIT"
    )  # on limit = 1, off = 0
    shutter_open_lim: EpicsSignalRO = Cpt(
        EpicsSignalRO, "-MO-DET-01:OPEN_LIMIT"
    )  # on limit = 1, off = 0
    z_disabled: EpicsSignalRO = Cpt(
        EpicsSignalRO, "-MO-DET-01:Z:DISABLED"
    )  # robot interlock, 0=ok to move, 1=blocked
    crate_power: EpicsSignalRO = Cpt(
        EpicsSignalRO, "-MO-PMAC-02:CRATE2_HEALTHY"
    )  # returns 0 if no power
    in_robot_load_safe_position: EpicsSignalRO = Cpt(
        EpicsSignalRO, "-MO-PMAC-02:GPIO_INP_BITS.B2"
    )  # returns 1 if safe
