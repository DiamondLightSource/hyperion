from __future__ import annotations

from typing import TYPE_CHECKING

import bluesky.plan_stubs as bps
from bluesky.preprocessors import finalize_decorator, stage_decorator, subs_decorator
from dodal import i03
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


def create_devices():
    global eiger, smargon, zebra

    eiger = i03.eiger(wait_for_connection=False)
    smargon = i03.smargon()
    zebra = i03.zebra()


DIRECTION = -1
OFFSET = 1
SHUTTER_OPENING_TIME = 0.5


def move_to_start_w_buffer(motors: Smargon, start_angle):
    yield from bps.abs_set(motors.omega.velocity, 120, wait=True)
    yield from bps.abs_set(
        motors.omega, start_angle - (OFFSET * DIRECTION), group="move_to_start"
    )


def move_to_end_w_buffer(motors: Smargon, scan_width):
    yield from bps.rel_set(
        motors.omega, ((scan_width + 0.1 + OFFSET) * DIRECTION), group="move_to_end"
    )


def set_speed(motors: Smargon, image_width, exposure_time):
    yield from bps.abs_set(
        motors.omega.velocity, image_width / exposure_time, group="set_speed"
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

    LOGGER.info(f"moving omega to {start_angle}")
    yield from move_to_start_w_buffer(smargon, start_angle)
    LOGGER.info("wait for any previous moves...")
    yield from bps.wait("move_to_start")
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
    )

    LOGGER.info(
        f"setting rotation speed for image_width, exposure_time {image_width, exposure_time} to {image_width/exposure_time}"
    )
    yield from set_speed(smargon, image_width, exposure_time)

    yield from arm_zebra(zebra)

    LOGGER.info(f"{'increase' if DIRECTION > 0 else 'decrease'} omega by {scan_width}")
    yield from move_to_end_w_buffer(smargon, scan_width)


def cleanup_plan(zebra):
    yield from disarm_zebra(zebra)


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
