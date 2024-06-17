from functools import wraps
from typing import Callable

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
from blueapi.core import MsgGenerator
from dodal.devices.zebra import (
    DISCONNECT,
    IN1_TTL,
    IN3_TTL,
    IN4_TTL,
    OR1,
    PC_PULSE,
    TTL_DETECTOR,
    TTL_PANDA,
    TTL_SHUTTER,
    TTL_XSPRESS3,
    ArmDemand,
    EncEnum,
    I03Axes,
    RotationDirection,
    SoftInState,
    Zebra,
)

from hyperion.log import LOGGER

ZEBRA_STATUS_TIMEOUT = 30


def bluesky_retry(func: Callable):
    """Decorator that will retry the decorated plan if it fails.

    Use this with care as it knows nothing about the state of the world when things fail.
    If it is possible that your plan fails when the beamline is in a transient state that
    the plan could not act on do not use this decorator without doing some more intelligent
    clean up.

    You should avoid using this decorator often in general production as it hides errors,
    instead it should be used only for debugging these underlying errors.
    """

    @wraps(func)
    def newfunc(*args, **kwargs):
        def log_and_retry(exception):
            LOGGER.error(f"Function {func.__name__} failed with {exception}, retrying")
            yield from func(*args, **kwargs)

        yield from bpp.contingency_wrapper(
            func(*args, **kwargs), except_plan=log_and_retry, auto_raise=False
        )

    return newfunc


def arm_zebra(zebra: Zebra):
    yield from bps.abs_set(zebra.pc.arm, ArmDemand.ARM, wait=True)


def disarm_zebra(zebra: Zebra):
    yield from bps.abs_set(zebra.pc.arm, ArmDemand.DISARM, wait=True)


@bluesky_retry
def setup_zebra_for_rotation(
    zebra: Zebra,
    axis: EncEnum = I03Axes.OMEGA,
    start_angle: float = 0,
    scan_width: float = 360,
    shutter_opening_deg: float = 2.5,
    shutter_opening_s: float = 0.04,
    direction: RotationDirection = RotationDirection.POSITIVE,
    group: str = "setup_zebra_for_rotation",
    wait: bool = True,
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
        direction:          RotationDirection enum for positive or negative.
                            Defaults to Positive.
        group:              A name for the group of statuses generated
        wait:               Block until all the settings have completed
    """
    if not isinstance(direction, RotationDirection):
        raise ValueError(
            "Disallowed rotation direction provided to Zebra setup plan. "
            "Use RotationDirection.POSITIVE or RotationDirection.NEGATIVE."
        )
    # TODO Actually set the rotation direction in here.
    # See https://github.com/DiamondLightSource/hyperion/issues/1273
    LOGGER.info("ZEBRA SETUP: START")
    # must be on for shutter trigger to be enabled
    yield from bps.abs_set(zebra.inputs.soft_in_1, SoftInState.YES, group=group)
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
    yield from bps.abs_set(zebra.output.pulse_1.input, DISCONNECT, group=group)
    LOGGER.info(f"ZEBRA SETUP: END - {'' if wait else 'not'} waiting for completion")
    if wait:
        yield from bps.wait(group, timeout=ZEBRA_STATUS_TIMEOUT)


@bluesky_retry
def setup_zebra_for_gridscan(zebra: Zebra, group="setup_zebra_for_gridscan", wait=True):
    yield from bps.abs_set(zebra.output.out_pvs[TTL_DETECTOR], IN3_TTL, group=group)
    yield from bps.abs_set(zebra.output.out_pvs[TTL_SHUTTER], IN4_TTL, group=group)
    yield from bps.abs_set(zebra.output.out_pvs[TTL_XSPRESS3], DISCONNECT, group=group)
    yield from bps.abs_set(zebra.output.pulse_1.input, DISCONNECT, group=group)

    if wait:
        yield from bps.wait(group, timeout=ZEBRA_STATUS_TIMEOUT)


@bluesky_retry
def set_zebra_shutter_to_manual(
    zebra: Zebra, group="set_zebra_shutter_to_manual", wait=True
) -> MsgGenerator:
    yield from bps.abs_set(zebra.output.out_pvs[TTL_DETECTOR], PC_PULSE, group=group)
    yield from bps.abs_set(zebra.output.out_pvs[TTL_SHUTTER], OR1, group=group)

    if wait:
        yield from bps.wait(group, timeout=ZEBRA_STATUS_TIMEOUT)


@bluesky_retry
def make_trigger_safe(zebra: Zebra, group="make_zebra_safe", wait=True):
    yield from bps.abs_set(
        zebra.inputs.soft_in_1, SoftInState.NO, wait=wait, group=group
    )


@bluesky_retry
def setup_zebra_for_panda_flyscan(
    zebra: Zebra, group="setup_zebra_for_panda_flyscan", wait=True
):
    # Forwards eiger trigger signal from panda
    yield from bps.abs_set(zebra.output.out_pvs[TTL_DETECTOR], IN1_TTL, group=group)

    # Forwards signal from PPMAC to fast shutter. High while panda PLC is running
    yield from bps.abs_set(zebra.output.out_pvs[TTL_SHUTTER], IN4_TTL, group=group)

    yield from bps.abs_set(zebra.output.out_pvs[3], DISCONNECT, group=group)

    yield from bps.abs_set(
        zebra.output.out_pvs[TTL_PANDA], IN3_TTL, group=group
    )  # Tells panda that motion is beginning/changing direction

    if wait:
        yield from bps.wait(group, timeout=ZEBRA_STATUS_TIMEOUT)
