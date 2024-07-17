from __future__ import annotations

import bluesky.plan_stubs as bps
from dodal.devices.aperturescatterguard import (
    AperturePositionGDANames,
    ApertureScatterguard,
)
from dodal.devices.attenuator import Attenuator
from dodal.devices.backlight import Backlight, BacklightPosition
from dodal.devices.detector.detector_motion import DetectorMotion
from dodal.devices.smargon import Smargon

from hyperion.log import LOGGER

LOWER_DETECTOR_SHUTTER_AFTER_SCAN = True


def begin_sample_environment_setup(
    detector_motion: DetectorMotion,
    attenuator: Attenuator,
    transmission_fraction: float,
    detector_distance: float,
    group="setup_senv",
):
    """Start all sample environment changes that can be initiated before OAV snapshots are taken"""
    yield from bps.abs_set(detector_motion.shutter, 1, group=group)
    yield from bps.abs_set(detector_motion.z, detector_distance, group=group)
    yield from bps.abs_set(attenuator, transmission_fraction, group=group)


def setup_sample_environment(
    aperture_scatterguard: ApertureScatterguard,
    aperture_position_gda_name: AperturePositionGDANames | None,
    backlight: Backlight,
    group="setup_senv",
):
    """Move the aperture into required position, move out the backlight."""

    yield from move_aperture_if_required(
        aperture_scatterguard, aperture_position_gda_name, group=group
    )
    yield from bps.abs_set(backlight, BacklightPosition.OUT, group=group)


def move_aperture_if_required(
    aperture_scatterguard: ApertureScatterguard,
    aperture_position_gda_name: AperturePositionGDANames | None,
    group="move_aperture",
):
    if not aperture_position_gda_name:
        previous_aperture_position = yield from bps.rd(aperture_scatterguard)
        assert isinstance(previous_aperture_position, dict)
        LOGGER.info(
            f"Using previously set aperture position {previous_aperture_position['name']}"
        )

    else:
        assert aperture_scatterguard.aperture_positions
        aperture_position = aperture_scatterguard.aperture_positions.get_position_from_gda_aperture_name(
            aperture_position_gda_name
        )
        LOGGER.info(f"Setting aperture position to {aperture_position}")
        yield from bps.abs_set(
            aperture_scatterguard,
            aperture_position,
            group=group,
        )


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

    LOGGER.info(f"Moving smargon to x, y, z: {(x, y, z)}")
    if x:
        yield from bps.abs_set(smargon.x, x, group=group)
    if y:
        yield from bps.abs_set(smargon.y, y, group=group)
    if z:
        yield from bps.abs_set(smargon.z, z, group=group)
    if wait:
        yield from bps.wait(group)


def move_phi_chi_omega(
    smargon: Smargon,
    phi: float | None = None,
    chi: float | None = None,
    omega: float | None = None,
    wait=False,
    group="move_phi_chi_omega",
):
    """Move the x, y, and z axes of the given smargon to the specified position. All
    axes are optional."""

    LOGGER.info(f"Moving smargon to phi, chi, omega: {(phi, chi, omega)}")
    if phi:
        yield from bps.abs_set(smargon.phi, phi, group=group)
    if chi:
        yield from bps.abs_set(smargon.chi, chi, group=group)
    if omega:
        yield from bps.abs_set(smargon.omega, omega, group=group)
    if wait:
        yield from bps.wait(group)
