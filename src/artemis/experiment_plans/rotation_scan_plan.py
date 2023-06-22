from __future__ import annotations

from typing import TYPE_CHECKING

import bluesky.plan_stubs as bps
from bluesky.preprocessors import (
    finalize_decorator,
    finalize_wrapper,
    stage_decorator,
    subs_decorator,
)
from dodal.beamlines import i03
from dodal.devices.backlight import Backlight
from dodal.devices.detector_motion import DetectorMotion
from dodal.devices.eiger import DetectorParams, EigerDetector
from dodal.devices.smargon import Smargon
from dodal.devices.zebra import RotationDirection, Zebra
from ophyd.epics_motor import EpicsMotor

from artemis.device_setup_plans.setup_zebra import (
    arm_zebra,
    disarm_zebra,
    setup_zebra_for_rotation,
)
from artemis.external_interaction.callbacks.rotation.rotation_callback_collection import (
    RotationCallbackCollection,
)
from artemis.log import LOGGER
from artemis.parameters.plan_specific.rotation_scan_internal_params import (
    RotationScanParams,
)

if TYPE_CHECKING:
    from artemis.parameters.plan_specific.rotation_scan_internal_params import (
        RotationInternalParameters,
    )


def create_devices():
    i03.eiger(wait_for_connection=False)
    i03.smargon()
    i03.zebra()
    i03.detector_motion()
    i03.backlight()


DIRECTION = RotationDirection.NEGATIVE
SHUTTER_OPENING_TIME = 0.5


def setup_sample_environment(
    detector_motion: DetectorMotion,
    backlight: Backlight,
    group="setup_senv",
):
    yield from bps.abs_set(detector_motion.shutter, 1, group=group)
    yield from bps.abs_set(backlight.pos, backlight.OUT, group=group)


def cleanup_sample_environment(
    zebra: Zebra,
    detector_motion: DetectorMotion,
    group="cleanup_senv",
):
    yield from bps.abs_set(zebra.inputs.soft_in_1, 0, group=group)
    yield from bps.abs_set(detector_motion.shutter, 0, group=group)


def move_to_start_w_buffer(
    axis: EpicsMotor,
    start_angle: float,
    offset: float,
    wait: bool = True,
    direction: RotationDirection = DIRECTION,
):
    """Move an EpicsMotor 'axis' to angle 'start_angle', modified by an offset and
    against the direction of rotation."""
    # can move to start as fast as possible
    # TODO get VMAX
    yield from bps.abs_set(axis.velocity, 90, wait=True)
    start_position = start_angle - (offset * direction)
    LOGGER.info(
        "moving to_start_w_buffer doing: start_angle-(offset*direction)"
        f" = {start_angle} - ({offset} * {direction}) = {start_position}"
    )
    yield from bps.abs_set(axis, start_position, group="move_to_start", wait=wait)


def move_to_end_w_buffer(
    axis: EpicsMotor,
    scan_width: float,
    offset: float,
    shutter_opening_degrees: float = 2.5,  # default for 100 deg/s
    wait: bool = True,
    direction: RotationDirection = DIRECTION,
):
    distance_to_move = (
        scan_width + shutter_opening_degrees + offset * 2 + 0.1
    ) * direction
    LOGGER.info(
        f"Given scan width of {scan_width}, acceleration offset of {offset}, direction"
        f" {direction}, apply a relative set to omega of: {distance_to_move}"
    )
    yield from bps.rel_set(axis, distance_to_move, group="move_to_end", wait=wait)


def set_speed(axis: EpicsMotor, image_width, exposure_time, wait=True):
    yield from bps.abs_set(
        axis.velocity, image_width / exposure_time, group="set_speed", wait=True
    )


def rotation_scan_plan(
    params: RotationInternalParameters,
    eiger: EigerDetector,
    smargon: Smargon,
    zebra: Zebra,
    backlight: Backlight,
    detector_motion: DetectorMotion,
):
    """A plan to collect diffraction images from a sample continuously rotating about
    a fixed axis - for now this axis is limited to omega."""
    detector_params: DetectorParams = params.artemis_params.detector_params
    expt_params: RotationScanParams = params.experiment_params

    start_angle = detector_params.omega_start
    scan_width = expt_params.get_num_images() * detector_params.omega_increment
    image_width = detector_params.omega_increment
    exposure_time = detector_params.exposure_time

    speed_for_rotation_deg_s = image_width / exposure_time
    LOGGER.info(f"calculated speed: {speed_for_rotation_deg_s} deg/s")

    # TODO get this from epics instead of hardcoded - time to velocity
    acceleration_offset = 0.15 * speed_for_rotation_deg_s
    LOGGER.info(
        f"calculated rotation offset for acceleration: at {speed_for_rotation_deg_s} "
        f"deg/s, to take 0.15s = {acceleration_offset}"
    )

    shutter_opening_degrees = (
        speed_for_rotation_deg_s * expt_params.shutter_opening_time_s
    )
    LOGGER.info(
        f"calculated degrees rotation needed for shutter: {shutter_opening_degrees} deg"
        f" for {expt_params.shutter_opening_time_s} at {speed_for_rotation_deg_s} deg/s"
    )

    LOGGER.info("setting up and staging eiger")

    yield from setup_sample_environment(detector_motion, backlight)
    LOGGER.info(f"moving omega to beginning, start_angle={start_angle}")
    yield from move_to_start_w_buffer(smargon.omega, start_angle, acceleration_offset)
    LOGGER.info("wait for any previous moves...")
    LOGGER.info(
        f"setting up zebra w: start_angle={start_angle}, scan_width={scan_width}"
    )
    yield from setup_zebra_for_rotation(
        zebra,
        start_angle=start_angle,
        scan_width=scan_width,
        direction=DIRECTION,
        shutter_opening_deg=shutter_opening_degrees,
        group="setup_zebra",
    )
    # wait for all the setup tasks at once
    yield from bps.wait("setup_senv")
    yield from bps.wait("move_to_start")
    yield from bps.wait("setup_zebra")

    LOGGER.info(
        f"setting rotation speed for image_width, exposure_time {image_width, exposure_time} to {image_width/exposure_time}"
    )
    yield from set_speed(smargon.omega, image_width, exposure_time, wait=True)

    yield from arm_zebra(zebra)

    LOGGER.info(
        f"{'increase' if DIRECTION > 0 else 'decrease'} omega through {scan_width}, to be modified by adjustments for shutter speed and acceleration"
    )
    yield from move_to_end_w_buffer(smargon.omega, scan_width, acceleration_offset)


def cleanup_plan(eiger, zebra, smargon, detector_motion, backlight):
    yield from cleanup_sample_environment(zebra, detector_motion)
    yield from finalize_wrapper(disarm_zebra(zebra), bps.wait("cleanup_senv"))


def get_plan(params: RotationInternalParameters):
    eiger = i03.eiger(wait_for_connection=False)
    smargon = i03.smargon()
    zebra = i03.zebra()
    detector_motion = i03.detector_motion()
    backlight = i03.backlight()
    devices = {
        "eiger": eiger,
        "smargon": smargon,
        "zebra": zebra,
        "detector_motion": detector_motion,
        "backlight": backlight,
    }
    subscriptions = RotationCallbackCollection.from_params(params)

    @subs_decorator(list(subscriptions))
    def rotation_scan_plan_with_stage_and_cleanup(
        params: RotationInternalParameters,
    ):
        eiger.set_detector_parameters(params.artemis_params.detector_params)

        @stage_decorator([eiger])
        @finalize_decorator(lambda: cleanup_plan(**devices))
        def rotation_with_cleanup_and_stage(params):
            yield from rotation_scan_plan(params, **devices)

        yield from rotation_with_cleanup_and_stage(params)

    yield from rotation_scan_plan_with_stage_and_cleanup(params)
