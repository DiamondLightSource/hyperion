import bluesky.plan_stubs as bps
from dodal.devices.zebra import (
    DISCONNECT,
    OR1,
    PC_PULSE,
    TTL_DETECTOR,
    TTL_SHUTTER,
    TTL_XSPRESS3,
    I03_axes,
    Zebra,
)


def setup_zebra_for_rotation(
    zebra: Zebra,
    axis: I03_axes = I03_axes.OMEGA,
    start_angle: float = 0,
    scan_width: float = 360,
    direction: int = 1,
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
        direction:          1 for positive direction or -1 for negative direction of
                            rotation. Other values cause a ValueError. Used for
                            adjusting the start angle based on shutter time.
        shutter_time_and_velocity: tuple[float, float] representing the time it takes
                        (in seconds) for the shutter to open and the velocity of the
                        scan (in deg/s). Used to ajust the gate start so that
    """
    if direction != 1 and direction != -1:
        raise ValueError("Direction must be 1 or -1")
    # Set gate start, adjust for shutter opening time if necessary
    if shutter_time_and_velocity[0] != 0:
        shutter_time = shutter_time_and_velocity[0]
        velocity = shutter_time_and_velocity[1]
        start_angle += direction * (shutter_time * velocity)
    yield from bps.abs_set(zebra.pc.gate_start, start_angle, group=group)
    # set gate width to total width
    yield from bps.abs_set(zebra.pc.gate_width, scan_width, group=group)
    # Set gate position to be angle of interest
    yield from bps.abs_set(zebra.pc.gate_trigger, axis.value, group=group)

    # Trigger the shutter with the gate (from PC_GATE & SOFTIN1 -> OR1)
    yield from bps.abs_set(zebra.output.out_pvs[TTL_SHUTTER], OR1, group=group)

    # Trigger the detector with a pulse
    yield from bps.abs_set(zebra.output.out_pvs[TTL_DETECTOR], PC_PULSE, group=group)

    yield from bps.abs_set(zebra.output.out_pvs[TTL_XSPRESS3], DISCONNECT, group=group)
    yield from bps.abs_set(zebra.output.pulse_1_input, DISCONNECT, group=group)

    if wait:
        bps.wait(group)
