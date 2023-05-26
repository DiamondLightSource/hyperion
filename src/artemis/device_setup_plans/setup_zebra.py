import bluesky.plan_stubs as bps
from dodal.devices.zebra import (
    DISCONNECT,
    IN3_TTL,
    IN4_TTL,
    OR1,
    PC_PULSE,
    TTL_DETECTOR,
    TTL_SHUTTER,
    TTL_XSPRESS3,
    I03Axes,
    RotationDirection,
    Zebra,
)

from artemis.log import LOGGER


def arm_zebra(zebra: Zebra, timeout: float = 3):
    yield from bps.abs_set(zebra.pc.arm_demand, 1)
    armed = yield from bps.rd(zebra.pc.armed)
    time = 0.0
    while not armed and time < timeout:
        armed = yield from bps.rd(zebra.pc.armed)
        time += 0.1
        yield from bps.sleep(0.1)
    if not armed:
        raise TimeoutError("Zebra failed to arm!")


def disarm_zebra(zebra: Zebra, timeout: float = 3):
    yield from bps.abs_set(zebra.pc.arm_demand, 0)
    armed = yield from bps.rd(zebra.pc.armed)
    time = 0.0
    while armed and time < timeout:
        armed = yield from bps.rd(zebra.pc.armed)
        time += 0.1
        yield from bps.sleep(0.1)
    if armed:
        raise TimeoutError("Zebra failed to disarm!")


def setup_zebra_for_rotation(
    zebra: Zebra,
    axis: I03Axes = I03Axes.OMEGA,
    start_angle: float = 0,
    scan_width: float = 360,
    direction: RotationDirection = RotationDirection.POSITIVE,
    shutter_time_and_velocity: tuple[float, float] = (0, 0),
    group: str = "setup_zebra_for_rotation",
    wait: bool = False,
):
    """Set up the Zebra to collect a rotation dataset. Any plan using this is
    responsible for setting the smargon velocity appropriately so that the desired
    image width is achieved with the exposure time given here.

    Parameters:
        axis:               I03 axes enum representing which axis to use for position
                            compare. Currently always omega.
        start_angle:        Position at which the scan should begin, in degrees.
        scan_width:         Total angle through which to collect, in degrees.
        direction:          RotationDirection enum for representing the direction of
                            rotation of the axis. Used for adjusting the start angle
                            based on shutter time.
        shutter_time_and_velocity: tuple[float, float] representing the time it takes
                        (in seconds) for the shutter to open and the velocity of the
                        scan (in deg/s). Used to ajust the gate start so that
    """
    if not isinstance(direction, RotationDirection):
        raise ValueError(
            "Disallowed rotation direction provided to Zebra setup plan. "
            "Use RotationDirection.POSITIVE or RotationDirection.NEGATIVE."
        )
    LOGGER.info("ZEBRA SETUP: START")
    # must be on for shutter trigger to be enabled
    yield from bps.abs_set(zebra.inputs.soft_in_1, 1, group=group)
    # Set gate start, adjust for shutter opening time if necessary
    LOGGER.info(f"ZEBRA SETUP: shutter_time_and_velocity = {shutter_time_and_velocity}")
    LOGGER.info(f"ZEBRA SETUP: start angle start: {start_angle}")
    LOGGER.info(f"ZEBRA SETUP: start angle adjusted, gate start set to: {start_angle}")
    yield from bps.abs_set(zebra.pc.gate_start, start_angle, group=group)
    # set gate width to total width
    yield from bps.abs_set(zebra.pc.gate_width, scan_width, group=group)
    # Set gate position to be angle of interest
    yield from bps.abs_set(zebra.pc.gate_trigger, axis.value, group=group)
    # Trigger the shutter with the gate (from PC_GATE & SOFTIN1 -> OR1)
    yield from bps.abs_set(zebra.output.out_pvs[TTL_SHUTTER], OR1, group=group)
    # Trigger the detector with a pulse
    yield from bps.abs_set(zebra.output.out_pvs[TTL_DETECTOR], PC_PULSE, group=group)
    # Don't use the fluorescence detector
    yield from bps.abs_set(zebra.output.out_pvs[TTL_XSPRESS3], DISCONNECT, group=group)
    yield from bps.abs_set(zebra.output.pulse_1_input, DISCONNECT, group=group)
    LOGGER.info(f"ZEBRA SETUP: END - {'' if wait else 'not'} waiting for completion")
    if wait:
        yield from bps.wait(group)


def setup_zebra_for_fgs(zebra: Zebra, group="setup_zebra_for_fgs", wait=False):
    yield from bps.abs_set(zebra.output.out_pvs[TTL_DETECTOR], IN3_TTL, group=group)
    yield from bps.abs_set(zebra.output.out_pvs[TTL_SHUTTER], IN4_TTL, group=group)
    yield from bps.abs_set(zebra.output.out_pvs[TTL_XSPRESS3], DISCONNECT, group=group)
    yield from bps.abs_set(zebra.output.pulse_1_input, DISCONNECT, group=group)

    if wait:
        yield from bps.wait(group)


def set_zebra_shutter_to_manual(
    zebra: Zebra, group="set_zebra_shutter_to_manual", wait=False
):
    yield from bps.abs_set(zebra.output.out_pvs[TTL_DETECTOR], PC_PULSE, group=group)
    yield from bps.abs_set(zebra.output.out_pvs[TTL_SHUTTER], OR1, group=group)

    if wait:
        yield from bps.wait(group)
