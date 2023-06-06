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

from artemis.device_setup_plans.read_hardware_for_setup import read_hardware_for_ispyb
from artemis.device_setup_plans.setup_zebra import (
    arm_zebra,
    disarm_zebra,
    setup_zebra_for_rotation,
)
from artemis.log import LOGGER
from artemis.parameters.plan_specific.rotation_scan_internal_params import (
    RotationScanParams,
)

if TYPE_CHECKING:
    from artemis.external_interaction.callbacks.rotation.rotation_callback_collection import (
        RotationCallbackCollection,
    )
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
OFFSET = 1
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


def move_to_start_w_buffer(axis: EpicsMotor, start_angle):
    """Move an EpicsMotor 'axis' to angle 'start_angle', modified by an offset and
    against the direction of rotation."""
    # can move to start as fast as possible
    yield from bps.abs_set(axis.velocity, 120, wait=True)
    start_position = start_angle - (OFFSET * DIRECTION)
    LOGGER.info(
        "moving to_start_w_buffer doing: start_angle-(offset*direction)"
        f" = {start_angle} - ({OFFSET} * {DIRECTION} = {start_position}"
    )

    yield from bps.abs_set(axis, start_position, group="move_to_start")


def move_to_end_w_buffer(axis: EpicsMotor, scan_width: float, wait: float = True):
    distance_to_move = (scan_width + 0.1 + OFFSET) * DIRECTION
    LOGGER.info(
        f"Given scan width of {scan_width}, offset of {OFFSET}, direction {DIRECTION}, apply a relative set to omega of: {distance_to_move}"
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

    LOGGER.info("setting up and staging eiger")

    yield from setup_sample_environment(detector_motion, backlight)
    LOGGER.info(f"moving omega to beginning, start_angle={start_angle}")
    yield from move_to_start_w_buffer(smargon.omega, start_angle)

    # get some information for the ispyb deposition and trigger the callback
    yield from read_hardware_for_ispyb(
        i03.undulator(),
        i03.synchrotron(),
        i03.s4_slit_gaps(),
    )

    LOGGER.info(
        f"setting up zebra w: start_angle={start_angle}, scan_width={scan_width}"
    )
    yield from setup_zebra_for_rotation(
        zebra,
        start_angle=start_angle,
        scan_width=scan_width,
        direction=DIRECTION,
        shutter_time_and_velocity=(
            SHUTTER_OPENING_TIME,
            image_width / exposure_time,
        ),
        group="setup_zebra",
    )

    LOGGER.info("wait for any previous moves...")
    # wait for all the setup tasks at once
    yield from bps.wait("setup_senv")
    yield from bps.wait("move_to_start")
    yield from bps.wait("setup_zebra")

    LOGGER.info(
        f"setting rotation speed for image_width, exposure_time {image_width, exposure_time} to {image_width/exposure_time}"
    )
    yield from set_speed(smargon.omega, image_width, exposure_time, wait=True)

    yield from arm_zebra(zebra)

    LOGGER.info(f"{'increase' if DIRECTION > 0 else 'decrease'} omega by {scan_width}")
    yield from move_to_end_w_buffer(smargon.omega, scan_width)


def cleanup_plan(eiger, zebra, smargon, detector_motion, backlight):
    yield from cleanup_sample_environment(zebra, detector_motion)
    yield from finalize_wrapper(disarm_zebra(zebra), bps.wait("cleanup_senv"))


def get_plan(
    params: RotationInternalParameters, subscriptions: RotationCallbackCollection
):
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
