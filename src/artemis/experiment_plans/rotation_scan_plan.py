from typing import TYPE_CHECKING

import bluesky.plan_stubs as bps
from bluesky.preprocessors import finalize_wrapper, stage_decorator
from dodal import i03

from artemis.device_setup_plans.setup_zebra_for_rotation import setup_zebra_for_rotation
from artemis.log import LOGGER

if TYPE_CHECKING:
    from dodal.devices.eiger import DetectorParams, EigerDetector
    from dodal.devices.rotation_scan import RotationScanParams
    from dodal.devices.smargon import Smargon
    from dodal.devices.zebra import Zebra

    from artemis.parameters.internal_parameters import InternalParameters


eiger: EigerDetector = None
smargon: Smargon = None
zebra: Zebra = None


def create_devices():
    global eiger, smargon, zebra

    eiger = i03.eiger()
    smargon = i03.smargon()
    zebra = i03.zebra()


DIRECTION = -1
OFFSET = 1
SHUTTER_OPENING_TIME = 0.5


def rotation_scan_plan(params: InternalParameters):
    def move_to_start_w_buffer(motors: Smargon, start_angle):
        yield from bps.abs_set(motors.omega.velocity, 100, wait=True)
        yield from bps.abs_set(motors.omega.velocity, 100, group="move_to_start")
        yield from bps.abs_set(
            motors.omega, start_angle - (OFFSET * DIRECTION), group="move_to_start"
        )

    def move_to_end_w_buffer(motors: Smargon, scan_width):
        yield from bps.rel_set(
            motors.omega, (scan_width + 0.1 + OFFSET) * DIRECTION, group="move_to_end"
        )

    def set_speed(motors: Smargon, image_width, exposure_time):
        yield from bps.abs_set(
            motors.omega.velocity, image_width / exposure_time, group="set_speed"
        )

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

    zebra.pc.arm()  # TODO planify this

    LOGGER.info(f"{'increase' if DIRECTION > 0 else 'decrease'} omega by {scan_width}")
    yield from move_to_end_w_buffer(smargon, scan_width)


def cleanup_plan():
    zebra.pc.disarm()


def get_plan(params: InternalParameters):
    def rotation_scan_plan_with_stage_and_cleanup(params):
        @stage_decorator(eiger)
        def with_cleanup(params):
            yield from finalize_wrapper(rotation_scan_plan(params), cleanup_plan())

        # TODO planify these
        eiger.set_detector_parameters()
        eiger.set_num_triggers_and_captures()
        yield from with_cleanup(params)

    yield from rotation_scan_plan_with_stage_and_cleanup(params)
