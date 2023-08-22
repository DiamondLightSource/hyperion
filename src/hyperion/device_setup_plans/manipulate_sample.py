from __future__ import annotations

import bluesky.plan_stubs as bps
from dodal.devices.attenuator import Attenuator
from dodal.devices.backlight import Backlight
from dodal.devices.detector_motion import DetectorMotion
from dodal.devices.smargon import Smargon

from hyperion.log import LOGGER

LOWER_DETECTOR_SHUTTER_AFTER_SCAN = True


def setup_sample_environment(
    detector_motion: DetectorMotion,
    backlight: Backlight,
    attenuator: Attenuator,
    transmission_fraction: float,
    detector_distance: float,
    group="setup_senv",
):
    """Move out the backlight, retract the detector shutter, and set the attenuator to
    transmission."""

    yield from bps.abs_set(detector_motion.shutter, 1, group=group)
    yield from bps.abs_set(detector_motion.z, detector_distance, group=group)
    yield from bps.abs_set(backlight.pos, backlight.OUT, group=group)
    yield from bps.abs_set(attenuator, transmission_fraction, group=group)


def cleanup_sample_environment(
    detector_motion: DetectorMotion,
    group="cleanup_senv",
):
    """Put the detector shutter back down"""

    yield from bps.abs_set(
        detector_motion.shutter,
        int(not LOWER_DETECTOR_SHUTTER_AFTER_SCAN),
        group=group,
    )


def move_x_y_z(
    smargon: Smargon,
    x: float | None = None,
    y: float | None = None,
    z: float | None = None,
    wait=False,
    group="move_x_y_z",
):
    """Move the x, y, and z axes of the given smargon to the specified position. All
    axes are optional."""

    LOGGER.info(f"Moving smargon to x, y, z: {(x,y,z)}")
    if x:
        yield from bps.abs_set(smargon.x, x, group=group)
    if y:
        yield from bps.abs_set(smargon.y, y, group=group)
    if z:
        yield from bps.abs_set(smargon.z, z, group=group)
    if wait:
        yield from bps.wait(group)
