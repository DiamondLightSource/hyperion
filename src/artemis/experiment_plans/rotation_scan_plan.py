from __future__ import annotations

from typing import TYPE_CHECKING

import bluesky.plan_stubs as bps
from bluesky.preprocessors import finalize_decorator, stage_decorator, subs_decorator
from dodal import i03
from dodal.devices.backlight import Backlight
from dodal.devices.detector_motion import Det as DetectorMotion
from dodal.devices.eiger import DetectorParams, EigerDetector
from dodal.devices.rotation_scan import RotationScanParams
from dodal.devices.smargon import Smargon
from dodal.devices.zebra import Zebra

from artemis.device_setup_plans.setup_zebra import (
    arm_zebra,
    disarm_zebra,
    setup_zebra_for_rotation,
)
from artemis.log import LOGGER

if TYPE_CHECKING:
    from artemis.external_interaction.callbacks.rotation.rotation_callback_collection import (
        RotationCallbackCollection,
    )
    from artemis.parameters.internal_parameters.plan_specific.rotation_scan_internal_params import (
        RotationInternalParameters,
    )


eiger: EigerDetector | None = None
smargon: Smargon | None = None
zebra: Zebra | None = None
detector_motion: DetectorMotion | None = None
backlight: Backlight | None = None


def create_devices():
    global eiger, smargon, zebra, detector_motion, backlight

    eiger = i03.eiger(wait_for_connection=False)
    smargon = i03.smargon()
    zebra = i03.zebra()
    detector_motion = DetectorMotion("BL03I")  # TODO fix after merging 554
    backlight = i03.backlight()


DIRECTION = -1
OFFSET = 1
SHUTTER_OPENING_TIME = 0.5


def setup_sample_environment(
    zebra: Zebra,
    detector_motion: DetectorMotion,
    backlight: Backlight,
    group="setup_senv",
):
    # must be on for shutter trigger to be enabled
    yield from bps.abs_set(zebra.inputs.soft_in_1, 1, group=group)
    yield from bps.abs_set(detector_motion.shutter, 1, group=group)
    yield from bps.abs_set(backlight.pos, backlight.OUT, group=group)


def cleanup_sample_environment(
    zebra: Zebra,
    detector_motion: DetectorMotion,
    group="cleanup_senv",
):
    yield from bps.abs_set(zebra.inputs.soft_in_1, 0, group=group)
    yield from bps.abs_set(detector_motion.shutter, 0, group=group)


def move_to_start_w_buffer(motors: Smargon, start_angle):
    yield from bps.abs_set(motors.omega.velocity, 120, wait=True)
    start_position = start_angle - (OFFSET * DIRECTION)
    LOGGER.info(
        "moving to_start_w_buffer doing: start_angle-(offset*direction)"
        f" = {start_angle} - ({OFFSET} * {DIRECTION} = {start_position}"
    )

    yield from bps.abs_set(motors.omega, start_position, group="move_to_start")


def move_to_end_w_buffer(motors: Smargon, scan_width: float, wait: float = True):
    distance_to_move = (scan_width + 0.1 + OFFSET) * DIRECTION
    LOGGER.info(
        f"Given scan width of {scan_width}, offset of {OFFSET}, direction {DIRECTION}, apply a relative set to omega of: {distance_to_move}"
    )
    yield from bps.rel_set(
        motors.omega, distance_to_move, group="move_to_end", wait=wait
    )


def set_speed(motors: Smargon, image_width, exposure_time, wait=True):
    yield from bps.abs_set(
        motors.omega.velocity, image_width / exposure_time, group="set_speed", wait=True
    )


def rotation_scan_plan(params: RotationInternalParameters):
    assert eiger is not None
    assert smargon is not None
    assert zebra is not None

    detector_params: DetectorParams = params.artemis_params.detector_params
    expt_params: RotationScanParams = params.experiment_params

    start_angle = detector_params.omega_start
    scan_width = expt_params.get_num_images() * detector_params.omega_increment
    image_width = detector_params.omega_increment
    exposure_time = detector_params.exposure_time

    LOGGER.info("setting up and staging eiger")

    LOGGER.info(f"moving omega to beginning, start_angle={start_angle}")
    yield from move_to_start_w_buffer(smargon, start_angle)
    LOGGER.info("wait for any previous moves...")
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
    yield from bps.wait("move_to_start")
    yield from bps.wait("setup_zebra")

    LOGGER.info(
        f"setting rotation speed for image_width, exposure_time {image_width, exposure_time} to {image_width/exposure_time}"
    )
    yield from set_speed(smargon, image_width, exposure_time, wait=True)

    yield from arm_zebra(zebra)

    LOGGER.info(f"{'increase' if DIRECTION > 0 else 'decrease'} omega by {scan_width}")
    yield from move_to_end_w_buffer(smargon, scan_width)


def cleanup_plan(zebra):
    yield from cleanup_sample_environment(zebra, detector_motion)
    try:
        yield from disarm_zebra(zebra)
    except Exception:
        yield from bps.wait("cleanup_senv")
        raise
    yield from bps.wait("cleanup_senv")


def get_plan(
    params: RotationInternalParameters, subscriptions: RotationCallbackCollection
):
    @subs_decorator(list(subscriptions))
    def rotation_scan_plan_with_stage_and_cleanup(params: RotationInternalParameters):
        assert eiger is not None
        assert smargon is not None
        assert zebra is not None

        @stage_decorator([eiger])
        @finalize_decorator(lambda: cleanup_plan(zebra))
        def rotation_with_cleanup_and_stage(params):
            yield from rotation_scan_plan(params)

        # TODO planify these
        eiger.set_detector_parameters(params.artemis_params.detector_params)
        eiger.set_num_triggers_and_captures()
        yield from rotation_with_cleanup_and_stage(params)

    yield from rotation_scan_plan_with_stage_and_cleanup(params)
