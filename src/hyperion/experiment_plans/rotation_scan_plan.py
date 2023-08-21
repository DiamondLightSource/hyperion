from __future__ import annotations

from typing import TYPE_CHECKING, Any

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
from blueapi.core import MsgGenerator
from dodal.beamlines import i03
from dodal.devices.detector import DetectorParams
from dodal.devices.detector_motion import DetectorMotion
from dodal.devices.eiger import DetectorParams, EigerDetector
from dodal.devices.smargon import Smargon
from dodal.devices.zebra import RotationDirection, Zebra
from hyperion.device_setup_plans.manipulate_sample import (
    cleanup_sample_environment,
    move_x_y_z,
    setup_sample_environment,
)
from hyperion.device_setup_plans.read_hardware_for_setup import read_hardware_for_ispyb
from hyperion.device_setup_plans.setup_zebra import (
    arm_zebra,
    disarm_zebra,
    make_trigger_safe,
    setup_zebra_for_rotation,
)
from hyperion.external_interaction.callbacks.rotation.rotation_callback_collection import (
    RotationCallbackCollection,
)
from hyperion.log import LOGGER
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationScanParams,
)
from ophyd.device import Device
from ophyd.epics_motor import EpicsMotor

if TYPE_CHECKING:
    from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
        RotationInternalParameters,
    )
    from ophyd.device import Device


def create_devices() -> dict[str, Device]:
    """Ensures necessary devices have been instantiated and returns a dict with
    references to them"""
    return {
        "eiger": i03.eiger(),
        "smargon": i03.smargon(),
        "zebra": i03.zebra(),
        "detector_motion": i03.detector_motion(),
        "backlight": i03.backlight(),
        "attenuator": i03.attenuator(),
    }


DEFAULT_DIRECTION = RotationDirection.NEGATIVE
DEFAULT_MAX_VELOCITY = 120
# Use a slightly larger time to accceleration than EPICS as it's better to be cautious
ACCELERATION_MARGIN = 1.5


def move_to_start_w_buffer(
    axis: EpicsMotor,
    start_angle: float,
    offset: float,
    wait_for_velocity_set: bool = True,
    wait_for_move: bool = False,
    direction: RotationDirection = DEFAULT_DIRECTION,
    max_velocity: float = DEFAULT_MAX_VELOCITY,
):
    """Move an EpicsMotor 'axis' to angle 'start_angle', modified by an offset and
    against the direction of rotation. Status for the move has group 'move_to_start'."""
    # can move to start as fast as possible
    # TODO get VMAX, see https://github.com/bluesky/ophyd/issues/1122
    yield from bps.abs_set(axis.velocity, max_velocity, wait=wait_for_velocity_set)
    start_position = start_angle - (offset * direction)
    LOGGER.info(
        "moving to_start_w_buffer doing: start_angle-(offset*direction)"
        f" = {start_angle} - ({offset} * {direction}) = {start_position}"
    )
    yield from bps.abs_set(
        axis, start_position, group="move_to_start", wait=wait_for_move
    )


def move_to_end_w_buffer(
    axis: EpicsMotor,
    scan_width: float,
    offset: float,
    shutter_opening_degrees: float,
    wait: bool = True,
    direction: RotationDirection = DEFAULT_DIRECTION,
):
    """Excecutes a rotation scan by moving the rotation axis from the beginning to
    the end; The Zebra should have been set up to trigger the detector for this to work.
    Rotates through 'scan width' plus twice an "offset" to take into account
    acceleration at the start and deceleration at the end, plus the number of extra
    degrees of rotation needed to make sure the fast shutter has fully opened before the
    detector trigger is sent.
    See https://github.com/DiamondLightSource/hyperion/wiki/rotation-scan-geometry
    for a simple pictorial explanation."""
    distance_to_move = (scan_width + shutter_opening_degrees + offset * 2) * direction
    LOGGER.info(
        f"Given scan width of {scan_width}, acceleration offset of {offset}, direction"
        f" {direction}, apply a relative set to omega of: {distance_to_move}"
    )
    yield from bps.rel_set(axis, distance_to_move, group="move_to_end", wait=wait)


def set_speed(axis: EpicsMotor, image_width, exposure_time, wait=True):
    speed_for_rotation = image_width / exposure_time
    yield from bps.abs_set(
        axis.velocity, speed_for_rotation, group="set_speed", wait=wait
    )


@bpp.set_run_key_decorator("rotation_scan_main")
@bpp.run_decorator(md={"subplan_name": "rotation_scan_main"})
def rotation_scan_plan(
    params: RotationInternalParameters,
    smargon: Smargon,
    zebra: Zebra,
    **kwargs,
):
    """A plan to collect diffraction images from a sample continuously rotating about
    a fixed axis - for now this axis is limited to omega. Only does the scan itself, no
    setup tasks."""

    detector_params: DetectorParams = params.hyperion_params.detector_params
    expt_params: RotationScanParams = params.experiment_params

    start_angle_deg = detector_params.omega_start
    scan_width_deg = expt_params.get_num_images() * detector_params.omega_increment
    image_width_deg = detector_params.omega_increment
    exposure_time_s = detector_params.exposure_time
    shutter_time_s = expt_params.shutter_opening_time_s

    speed_for_rotation_deg_s = image_width_deg / exposure_time_s
    LOGGER.info(f"calculated speed: {speed_for_rotation_deg_s} deg/s")

    motor_time_to_speed = yield from bps.rd(smargon.omega.acceleration)
    motor_time_to_speed *= ACCELERATION_MARGIN
    acceleration_offset = motor_time_to_speed * speed_for_rotation_deg_s
    LOGGER.info(
        f"calculated rotation offset for acceleration: at {speed_for_rotation_deg_s} "
        f"deg/s, to take {motor_time_to_speed} s = {acceleration_offset} deg"
    )

    shutter_opening_degrees = (
        speed_for_rotation_deg_s * expt_params.shutter_opening_time_s
    )
    LOGGER.info(
        f"calculated degrees rotation needed for shutter: {shutter_opening_degrees} deg"
        f" for {shutter_time_s} s at {speed_for_rotation_deg_s} deg/s"
    )

    LOGGER.info(f"moving omega to beginning, start_angle={start_angle_deg}")
    yield from move_to_start_w_buffer(
        smargon.omega, start_angle_deg, acceleration_offset
    )

    LOGGER.info(
        f"setting up zebra w: start_angle = {start_angle_deg} deg, "
        f"scan_width = {scan_width_deg} deg"
    )
    yield from setup_zebra_for_rotation(
        zebra,
        start_angle=start_angle_deg,
        scan_width=scan_width_deg,
        direction=expt_params.rotation_direction,
        shutter_opening_deg=shutter_opening_degrees,
        shutter_opening_s=expt_params.shutter_opening_time_s,
        group="setup_zebra",
    )

    LOGGER.info("wait for any previous moves...")
    # wait for all the setup tasks at once
    yield from bps.wait("setup_senv")
    yield from bps.wait("move_x_y_z")
    yield from bps.wait("move_to_start")
    yield from bps.wait("setup_zebra")

    # get some information for the ispyb deposition and trigger the callback
    yield from read_hardware_for_ispyb(
        i03.undulator(),
        i03.synchrotron(),
        i03.s4_slit_gaps(),
        i03.attenuator(),
        i03.flux(),
    )

    LOGGER.info(
        f"Based on image_width {image_width_deg} deg, exposure_time {exposure_time_s}"
        f" s, setting rotation speed to {image_width_deg/exposure_time_s} deg/s"
    )
    yield from set_speed(smargon.omega, image_width_deg, exposure_time_s, wait=True)

    yield from arm_zebra(zebra)

    LOGGER.info(
        f"{'increase' if expt_params.rotation_direction > 0 else 'decrease'} omega "
        f"through {scan_width_deg}, (before shutter and acceleration adjustment)"
    )
    yield from move_to_end_w_buffer(
        smargon.omega, scan_width_deg, shutter_opening_degrees, acceleration_offset
    )

    LOGGER.info(f"resetting omega velocity to {DEFAULT_MAX_VELOCITY}")
    yield from bps.abs_set(smargon.omega.velocity, DEFAULT_MAX_VELOCITY)


def cleanup_plan(
    zebra: Zebra, smargon: Smargon, detector_motion: DetectorMotion, **kwargs
):
    yield from cleanup_sample_environment(detector_motion, group="cleanup")
    yield from bps.abs_set(
        smargon.omega.velocity, DEFAULT_MAX_VELOCITY, group="cleanup"
    )
    yield from make_trigger_safe(zebra, group="cleanup")
    yield from bpp.finalize_wrapper(disarm_zebra(zebra), bps.wait("cleanup"))


def rotation_scan(parameters: Any) -> MsgGenerator:
    devices = create_devices()
    subscriptions = RotationCallbackCollection.from_params(parameters)

    @bpp.subs_decorator(list(subscriptions))
    @bpp.set_run_key_decorator("rotation_scan")
    @bpp.run_decorator(  # attach experiment metadata to the start document
        md={
            "subplan_name": "rotation_scan_with_cleanup",
            "hyperion_internal_parameters": parameters.json(),
        }
    )
    def rotation_scan_plan_with_stage_and_cleanup(
        params: RotationInternalParameters,
    ):
        eiger: EigerDetector = devices["eiger"]
        eiger.set_detector_parameters(params.hyperion_params.detector_params)

        @bpp.stage_decorator([eiger])
        @bpp.finalize_decorator(lambda: cleanup_plan(**devices))
        def rotation_with_cleanup_and_stage(params: RotationInternalParameters):
            LOGGER.info("setting up sample environment...")
            yield from setup_sample_environment(
                devices["detector_motion"],
                devices["backlight"],
                devices["attenuator"],
                params.hyperion_params.ispyb_params.transmission_fraction,
                params.hyperion_params.detector_params.detector_distance,
            )
            LOGGER.info("moving to position (if specified)")
            yield from move_x_y_z(
                devices["smargon"],
                params.experiment_params.x,
                params.experiment_params.y,
                params.experiment_params.z,
                group="move_x_y_z",
            )

            yield from rotation_scan_plan(params, **devices)

        LOGGER.info("setting up and staging eiger...")
        yield from rotation_with_cleanup_and_stage(params)

    yield from rotation_scan_plan_with_stage_and_cleanup(parameters)
