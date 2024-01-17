import bluesky.plan_stubs as bps
from dodal.devices.zebra import (
    DISCONNECT,
    IN1_TTL,
    IN2_TTL,
    IN3_TTL,
    IN4_TTL,
    OR1,
    PC_PULSE,
    TTL_DETECTOR,
    TTL_PANDA,
    TTL_SHUTTER,
    TTL_XSPRESS3,
    ArmDemand,
    I03Axes,
    RotationDirection,
    Zebra,
)

from hyperion.log import LOGGER


def arm_zebra(zebra: Zebra):
    yield from bps.abs_set(zebra.pc.arm, ArmDemand.ARM, wait=True)


def disarm_zebra(zebra: Zebra):
    yield from bps.abs_set(zebra.pc.arm, ArmDemand.DISARM, wait=True)


def setup_zebra_for_rotation(
    zebra: Zebra,
    axis: I03Axes = I03Axes.OMEGA,
    start_angle: float = 0,
    scan_width: float = 360,
    shutter_opening_deg: float = 2.5,
    shutter_opening_s: float = 0.04,
    direction: RotationDirection = RotationDirection.POSITIVE,
    group: str = "setup_zebra_for_rotation",
    wait: bool = False,
):
    """Set up the Zebra to collect a rotation dataset. Any plan using this is
    responsible for setting the smargon velocity appropriately so that the desired
    image width is achieved with the exposure time given here.

    Parameters:
        zebra:              The zebra device to use
        axis:               I03 axes enum representing which axis to use for position
                            compare. Currently always omega.
        start_angle:        Position at which the scan should begin, in degrees.
        scan_width:         Total angle through which to collect, in degrees.
        shutter_opening_deg:How many degrees of rotation it takes for the fast shutter
                            to open. Increases the gate width.
        shutter_opening_s:  How many seconds it takes for the fast shutter to open. The
                            detector pulse is delayed after the shutter signal by this
                            amount.
        direction:          RotationDirection enum for positive or negative
        group:              A name for the group of statuses generated
        wait:               Block until all the settings have completed
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
    LOGGER.info(f"ZEBRA SETUP: degrees to adjust for shutter = {shutter_opening_deg}")
    LOGGER.info(f"ZEBRA SETUP: start angle start: {start_angle}")
    LOGGER.info(f"ZEBRA SETUP: start angle adjusted, gate start set to: {start_angle}")
    yield from bps.abs_set(zebra.pc.gate_start, start_angle, group=group)
    # set gate width to total width
    yield from bps.abs_set(
        zebra.pc.gate_width, scan_width + shutter_opening_deg, group=group
    )
    LOGGER.info(
        f"Pulse start set to shutter open time, set to: {abs(shutter_opening_s)}"
    )
    yield from bps.abs_set(zebra.pc.pulse_start, abs(shutter_opening_s), group=group)
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


def setup_zebra_for_gridscan(
    zebra: Zebra, group="setup_zebra_for_gridscan", wait=False
):
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


def make_trigger_safe(zebra: Zebra, group="make_zebra_safe", wait=False):
    yield from bps.abs_set(zebra.inputs.soft_in_1, 0, wait=wait, group=group)


def setup_zebra_for_panda_flyscan(
    zebra: Zebra, group="setup_zebra_for_panda_flyscan", wait=False
):
    yield from bps.abs_set(
        zebra.output.out_pvs[TTL_DETECTOR], IN1_TTL, group=group
    )  # Forwards eiger trigger signal from panda

    yield from bps.abs_set(
        zebra.output.out_pvs[TTL_SHUTTER], IN2_TTL, group=group
    )  # Forwards shutter trigger signal from panda

    yield from bps.abs_set(zebra.output.out_pvs[3], DISCONNECT, group=group)

    yield from bps.abs_set(
        zebra.output.out_pvs[TTL_PANDA], IN3_TTL, group=group
    )  # Tells panda that motion is beginning/changing direction

    if wait:
        yield from bps.wait(group)
