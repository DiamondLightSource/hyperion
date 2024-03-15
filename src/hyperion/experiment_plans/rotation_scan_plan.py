from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
from blueapi.core import BlueskyContext, MsgGenerator
from dodal.devices.aperturescatterguard import ApertureScatterguard
from dodal.devices.attenuator import Attenuator
from dodal.devices.backlight import Backlight
from dodal.devices.DCM import DCM
from dodal.devices.detector import DetectorParams
from dodal.devices.detector.detector_motion import DetectorMotion
from dodal.devices.eiger import EigerDetector
from dodal.devices.flux import Flux
from dodal.devices.robot import BartRobot
from dodal.devices.s4_slit_gaps import S4SlitGaps
from dodal.devices.smargon import Smargon
from dodal.devices.synchrotron import Synchrotron
from dodal.devices.undulator import Undulator
from dodal.devices.zebra import RotationDirection, Zebra

from hyperion.device_setup_plans.check_topup import check_topup_and_wait_if_necessary
from hyperion.device_setup_plans.manipulate_sample import (
    cleanup_sample_environment,
    move_x_y_z,
    setup_sample_environment,
)
from hyperion.device_setup_plans.read_hardware_for_setup import (
    read_hardware_for_ispyb_during_collection,
    read_hardware_for_ispyb_pre_collection,
    read_hardware_for_nexus_writer,
    read_hardware_for_zocalo,
)
from hyperion.device_setup_plans.setup_zebra import (
    arm_zebra,
    disarm_zebra,
    make_trigger_safe,
    setup_zebra_for_rotation,
)
from hyperion.log import LOGGER
from hyperion.parameters.constants import CONST
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationScanParams,
)
from hyperion.utils.context import device_composite_from_context

if TYPE_CHECKING:
    from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
        RotationInternalParameters,
    )


@dataclasses.dataclass
class RotationScanComposite:
    """All devices which are directly or indirectly required by this plan"""

    aperture_scatterguard: ApertureScatterguard
    attenuator: Attenuator
    backlight: Backlight
    dcm: DCM
    detector_motion: DetectorMotion
    eiger: EigerDetector
    flux: Flux
    robot: BartRobot
    smargon: Smargon
    undulator: Undulator
    synchrotron: Synchrotron
    s4_slit_gaps: S4SlitGaps
    zebra: Zebra


def create_devices(context: BlueskyContext) -> RotationScanComposite:
    """Ensures necessary devices have been instantiated"""

    return device_composite_from_context(context, RotationScanComposite)


DEFAULT_DIRECTION = RotationDirection.NEGATIVE
DEFAULT_MAX_VELOCITY = 120
# Use a slightly larger time to acceleration than EPICS as it's better to be cautious
ACCELERATION_MARGIN = 1.5


@dataclasses.dataclass
class RotationMotionProfile:
    start_scan_deg: float
    start_motion_deg: float
    scan_width_deg: float
    shutter_time_s: float
    direction: RotationDirection
    speed_for_rotation_deg_s: float
    acceleration_offset_deg: float
    shutter_opening_deg: float
    total_exposure_s: float
    distance_to_move_deg: float
    max_velocity_deg_s: float


def calculate_motion_profile(
    detector_params: DetectorParams,
    expt_params: RotationScanParams,
    motor_time_to_speed_s: float,
    max_velocity_deg_s: float,
) -> RotationMotionProfile:
    """Calculates the various numbers needed for motions in the rotation scan.
    Rotates through "scan width" plus twice an "offset" to take into account
    acceleration at the start and deceleration at the end, plus the number of extra
    degrees of rotation needed to make sure the fast shutter has fully opened before the
    detector trigger is sent.
    See https://github.com/DiamondLightSource/hyperion/wiki/rotation-scan-geometry
    for a simple pictorial explanation."""

    direction = expt_params.rotation_direction
    num_images = expt_params.get_num_images()
    shutter_time_s = expt_params.shutter_opening_time_s
    image_width_deg = detector_params.omega_increment
    exposure_time_s = detector_params.exposure_time
    motor_time_to_speed_s *= ACCELERATION_MARGIN
    start_scan_deg = detector_params.omega_start

    LOGGER.info("Calculating rotation scan motion profile:")
    LOGGER.info(
        f"{num_images=}, {shutter_time_s=}, {image_width_deg=}, {exposure_time_s=}, {direction=}"
    )
    LOGGER.info(f"{(scan_width_deg := num_images * detector_params.omega_increment)=}")
    LOGGER.info(f"{(speed_for_rotation_deg_s := image_width_deg / exposure_time_s)=}")
    LOGGER.info(
        f"{(acceleration_offset_deg := motor_time_to_speed_s * speed_for_rotation_deg_s)=}"
    )
    LOGGER.info(
        f"{(start_motion_deg := start_scan_deg - (acceleration_offset_deg * direction))=}"
    )
    LOGGER.info(
        f"{(shutter_opening_deg := speed_for_rotation_deg_s * expt_params.shutter_opening_time_s)=}"
    )
    LOGGER.info(f"{(total_exposure_s := num_images * exposure_time_s)=}")
    LOGGER.info(
        f"{(distance_to_move_deg := (scan_width_deg + shutter_opening_deg + acceleration_offset_deg * 2) * direction)=}"
    )

    return RotationMotionProfile(
        start_scan_deg=start_scan_deg,
        start_motion_deg=start_motion_deg,
        scan_width_deg=scan_width_deg,
        shutter_time_s=shutter_time_s,
        direction=direction,
        speed_for_rotation_deg_s=speed_for_rotation_deg_s,
        acceleration_offset_deg=acceleration_offset_deg,
        shutter_opening_deg=shutter_opening_deg,
        total_exposure_s=total_exposure_s,
        distance_to_move_deg=distance_to_move_deg,
        max_velocity_deg_s=max_velocity_deg_s,
    )


def rotation_scan_plan(
    composite: RotationScanComposite,
    params: RotationInternalParameters,
    motion_values: RotationMotionProfile,
):
    """A plan to collect diffraction images from a sample continuously rotating about
    a fixed axis - for now this axis is limited to omega. Only does the scan itself, no
    setup tasks."""

    @bpp.set_run_key_decorator(CONST.PLAN.ROTATION_MAIN)
    @bpp.run_decorator(
        md={
            "subplan_name": CONST.PLAN.ROTATION_MAIN,
            "zocalo_environment": params.hyperion_params.zocalo_environment,
            "scan_points": [params.get_scan_points()],
        }
    )
    def _rotation_scan_plan(
        motion_values: RotationMotionProfile, composite: RotationScanComposite
    ):
        axis = composite.smargon.omega

        LOGGER.info(f"moving omega to beginning, {motion_values.start_scan_deg=}")
        # can move to start as fast as possible
        # TODO get VMAX, see https://github.com/bluesky/ophyd/issues/1122
        yield from bps.abs_set(
            axis.velocity, motion_values.max_velocity_deg_s, wait=True
        )
        yield from bps.abs_set(
            axis,
            motion_values.start_motion_deg,
            group="move_to_start",
            wait=True,
        )
        yield from setup_zebra_for_rotation(
            composite.zebra,
            start_angle=motion_values.start_scan_deg,
            scan_width=motion_values.scan_width_deg,
            direction=motion_values.direction,
            shutter_opening_deg=motion_values.shutter_opening_deg,
            shutter_opening_s=motion_values.shutter_time_s,
            group="setup_zebra",
            wait=True,
        )

        LOGGER.info("Wait for any previous moves...")
        # wait for all the setup tasks at once
        yield from bps.wait("setup_senv")
        yield from bps.wait("move_x_y_z")
        yield from bps.wait("move_to_start")
        yield from bps.wait("setup_zebra")

        # get some information for the ispyb deposition and trigger the callback
        yield from read_hardware_for_zocalo(composite.eiger)

        yield from read_hardware_for_ispyb_pre_collection(
            composite.undulator,
            composite.synchrotron,
            composite.s4_slit_gaps,
            composite.aperture_scatterguard,
            composite.robot,
        )
        yield from read_hardware_for_ispyb_during_collection(
            composite.attenuator, composite.flux, composite.dcm
        )
        yield from read_hardware_for_nexus_writer(composite.eiger)

        # Get ready for the actual scan
        yield from bps.abs_set(
            axis.velocity, motion_values.speed_for_rotation_deg_s, wait=True
        )
        yield from arm_zebra(composite.zebra)

        # Check topup gate
        yield from check_topup_and_wait_if_necessary(
            composite.synchrotron,
            motion_values.total_exposure_s,
            ops_time=10.0,  # Additional time to account for rotation, is s
        )  # See #https://github.com/DiamondLightSource/hyperion/issues/932

        LOGGER.info("Executing rotation scan")
        yield from bps.rel_set(axis, motion_values.distance_to_move_deg, wait=True)

    yield from _rotation_scan_plan(motion_values, composite)


def cleanup_plan(composite: RotationScanComposite, max_vel: float, **kwargs):
    LOGGER.info("Cleaning up after rotation scan")
    yield from cleanup_sample_environment(composite.detector_motion, group="cleanup")
    yield from bps.abs_set(composite.smargon.omega.velocity, max_vel, group="cleanup")
    yield from make_trigger_safe(composite.zebra, group="cleanup")
    yield from bpp.finalize_wrapper(disarm_zebra(composite.zebra), bps.wait("cleanup"))


def rotation_scan(composite: RotationScanComposite, parameters: Any) -> MsgGenerator:
    @bpp.set_run_key_decorator("rotation_scan")
    @bpp.run_decorator(  # attach experiment metadata to the start document
        md={
            "subplan_name": CONST.PLAN.ROTATION_OUTER,
            CONST.TRIGGER.ZOCALO: CONST.PLAN.ROTATION_MAIN,
            "hyperion_internal_parameters": parameters.json(),
            "activate_callbacks": [
                "RotationISPyBCallback",
                "RotationNexusFileCallback",
            ],
        }
    )
    def rotation_scan_plan_with_stage_and_cleanup(
        params: RotationInternalParameters,
    ):
        motor_time_to_speed = yield from bps.rd(composite.smargon.omega.acceleration)
        max_vel = (
            yield from bps.rd(composite.smargon.omega.max_velocity)
            or DEFAULT_MAX_VELOCITY
        )
        motion_values = calculate_motion_profile(
            params.hyperion_params.detector_params,
            params.experiment_params,
            motor_time_to_speed,
            max_vel,
        )

        eiger: EigerDetector = composite.eiger
        eiger.set_detector_parameters(params.hyperion_params.detector_params)

        @bpp.stage_decorator([eiger])
        @bpp.finalize_decorator(lambda: cleanup_plan(composite, max_vel))
        def rotation_with_cleanup_and_stage(params: RotationInternalParameters):
            LOGGER.info("setting up sample environment...")
            yield from setup_sample_environment(
                composite.detector_motion,
                composite.backlight,
                composite.attenuator,
                params.hyperion_params.ispyb_params.transmission_fraction,
                params.hyperion_params.detector_params.detector_distance,
            )
            LOGGER.info("moving to position (if specified)")
            yield from move_x_y_z(
                composite.smargon,
                params.experiment_params.x,
                params.experiment_params.y,
                params.experiment_params.z,
                group="move_x_y_z",
            )
            yield from rotation_scan_plan(
                composite,
                params,
                motion_values,
            )

        LOGGER.info("setting up and staging eiger...")
        yield from rotation_with_cleanup_and_stage(params)

    yield from rotation_scan_plan_with_stage_and_cleanup(parameters)
