from __future__ import annotations

import dataclasses

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
from blueapi.core import BlueskyContext, MsgGenerator
from dodal.devices.aperturescatterguard import ApertureScatterguard
from dodal.devices.attenuator import Attenuator
from dodal.devices.backlight import Backlight
from dodal.devices.dcm import DCM
from dodal.devices.detector.detector_motion import DetectorMotion
from dodal.devices.eiger import EigerDetector
from dodal.devices.flux import Flux
from dodal.devices.oav.oav_detector import OAV
from dodal.devices.oav.oav_parameters import OAVParameters
from dodal.devices.robot import BartRobot
from dodal.devices.s4_slit_gaps import S4SlitGaps
from dodal.devices.smargon import Smargon
from dodal.devices.synchrotron import Synchrotron
from dodal.devices.undulator import Undulator
from dodal.devices.zebra import RotationDirection, Zebra
from dodal.plans.check_topup import check_topup_and_wait_if_necessary

from hyperion.device_setup_plans.manipulate_sample import (
    begin_sample_environment_setup,
    cleanup_sample_environment,
    move_phi_chi_omega,
    move_x_y_z,
    setup_sample_environment,
)
from hyperion.device_setup_plans.read_hardware_for_setup import (
    read_hardware_during_collection,
    read_hardware_for_zocalo,
    read_hardware_pre_collection,
)
from hyperion.device_setup_plans.setup_zebra import (
    arm_zebra,
    disarm_zebra,
    make_trigger_safe,
    setup_zebra_for_rotation,
)
from hyperion.experiment_plans.oav_snapshot_plan import (
    OavSnapshotComposite,
    oav_snapshot_plan,
    setup_oav_snapshot_plan,
)
from hyperion.log import LOGGER
from hyperion.parameters.constants import CONST
from hyperion.parameters.rotation import (
    MultiRotationScan,
    RotationScan,
)
from hyperion.utils.aperturescatterguard import (
    load_default_aperture_scatterguard_positions_if_unset,
)
from hyperion.utils.context import device_composite_from_context


@dataclasses.dataclass
class RotationScanComposite(OavSnapshotComposite):
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
    oav: OAV

    def __post_init__(self):
        """Ensure that aperture positions are loaded whenever this class is created."""
        load_default_aperture_scatterguard_positions_if_unset(
            self.aperture_scatterguard
        )


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
    params: RotationScan,
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

    direction = params.rotation_direction.multiplier
    num_images = params.num_images
    shutter_time_s = params.shutter_opening_time_s
    image_width_deg = params.rotation_increment_deg
    exposure_time_s = params.exposure_time_s
    motor_time_to_speed_s *= ACCELERATION_MARGIN
    start_scan_deg = params.omega_start_deg

    LOGGER.info("Calculating rotation scan motion profile:")
    LOGGER.info(
        f"{num_images=}, {shutter_time_s=}, {image_width_deg=}, {exposure_time_s=}, {direction=}"
    )

    scan_width_deg = num_images * params.rotation_increment_deg
    LOGGER.info("scan_width_deg = num_images * params.rotation_increment_deg")
    LOGGER.info(f"{scan_width_deg} = {num_images} * {params.rotation_increment_deg}")

    speed_for_rotation_deg_s = image_width_deg / exposure_time_s
    LOGGER.info("speed_for_rotation_deg_s = image_width_deg / exposure_time_s")
    LOGGER.info(f"{speed_for_rotation_deg_s} = {image_width_deg} / {exposure_time_s}")

    acceleration_offset_deg = motor_time_to_speed_s * speed_for_rotation_deg_s
    LOGGER.info(
        "acceleration_offset_deg = motor_time_to_speed_s * speed_for_rotation_deg_s"
    )
    LOGGER.info(
        f"{acceleration_offset_deg} = {motor_time_to_speed_s} * {speed_for_rotation_deg_s}"
    )

    start_motion_deg = start_scan_deg - (acceleration_offset_deg * direction)
    LOGGER.info(
        "start_motion_deg = start_scan_deg - (acceleration_offset_deg * direction)"
    )
    LOGGER.info(
        f"{start_motion_deg} = {start_scan_deg} - ({acceleration_offset_deg} * {direction})"
    )

    shutter_opening_deg = speed_for_rotation_deg_s * shutter_time_s
    LOGGER.info("shutter_opening_deg = speed_for_rotation_deg_s * shutter_time_s")
    LOGGER.info(
        f"{shutter_opening_deg} = {speed_for_rotation_deg_s} * {shutter_time_s}"
    )

    shutter_opening_deg = speed_for_rotation_deg_s * shutter_time_s
    LOGGER.info("shutter_opening_deg = speed_for_rotation_deg_s * shutter_time_s")
    LOGGER.info(
        f"{shutter_opening_deg} = {speed_for_rotation_deg_s} * {shutter_time_s}"
    )

    total_exposure_s = num_images * exposure_time_s
    LOGGER.info("total_exposure_s = num_images * exposure_time_s")
    LOGGER.info(f"{total_exposure_s} = {num_images} * {exposure_time_s}")

    distance_to_move_deg = (
        scan_width_deg + shutter_opening_deg + acceleration_offset_deg * 2
    ) * direction
    LOGGER.info(
        "distance_to_move_deg = (scan_width_deg + shutter_opening_deg + acceleration_offset_deg * 2) * direction)"
    )
    LOGGER.info(
        f"{distance_to_move_deg} = ({scan_width_deg} + {shutter_opening_deg} + {acceleration_offset_deg} * 2) * {direction})"
    )

    return RotationMotionProfile(
        start_scan_deg=start_scan_deg,
        start_motion_deg=start_motion_deg,
        scan_width_deg=scan_width_deg,
        shutter_time_s=shutter_time_s,
        direction=params.rotation_direction,
        speed_for_rotation_deg_s=speed_for_rotation_deg_s,
        acceleration_offset_deg=acceleration_offset_deg,
        shutter_opening_deg=shutter_opening_deg,
        total_exposure_s=total_exposure_s,
        distance_to_move_deg=distance_to_move_deg,
        max_velocity_deg_s=max_velocity_deg_s,
    )


def rotation_scan_plan(
    composite: RotationScanComposite,
    params: RotationScan,
    motion_values: RotationMotionProfile,
):
    """A stub plan to collect diffraction images from a sample continuously rotating
    about a fixed axis - for now this axis is limited to omega.
    Needs additional setup of the sample environment and a wrapper to clean up."""

    @bpp.set_run_key_decorator(CONST.PLAN.ROTATION_MAIN)
    @bpp.run_decorator(
        md={
            "subplan_name": CONST.PLAN.ROTATION_MAIN,
            "scan_points": [params.scan_points],
        }
    )
    def _rotation_scan_plan(
        motion_values: RotationMotionProfile,
        composite: RotationScanComposite,
    ):
        axis = composite.smargon.omega

        # can move to start as fast as possible
        yield from bps.abs_set(
            axis.velocity, motion_values.max_velocity_deg_s, wait=True
        )
        LOGGER.info(f"moving omega to beginning, {motion_values.start_scan_deg=}")
        yield from bps.abs_set(
            axis,
            motion_values.start_motion_deg,
            group="move_to_rotation_start",
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

        yield from setup_sample_environment(
            composite.aperture_scatterguard,
            params.selected_aperture,
            composite.backlight,
        )

        LOGGER.info("Wait for any previous moves...")
        # wait for all the setup tasks at once
        yield from bps.wait(CONST.WAIT.MOVE_GONIO_TO_START)
        yield from bps.wait("setup_senv")
        yield from bps.wait("move_to_rotation_start")

        # get some information for the ispyb deposition and trigger the callback
        yield from read_hardware_for_zocalo(composite.eiger)

        yield from read_hardware_pre_collection(
            composite.undulator,
            composite.synchrotron,
            composite.s4_slit_gaps,
            composite.robot,
            composite.smargon,
        )

        # Get ready for the actual scan
        yield from bps.abs_set(
            axis.velocity, motion_values.speed_for_rotation_deg_s, wait=True
        )

        yield from bps.wait("setup_zebra")
        yield from arm_zebra(composite.zebra)

        # Check topup gate
        yield from check_topup_and_wait_if_necessary(
            composite.synchrotron,
            motion_values.total_exposure_s,
            ops_time=10.0,  # Additional time to account for rotation, is s
        )  # See #https://github.com/DiamondLightSource/hyperion/issues/932

        LOGGER.info("Executing rotation scan")
        yield from bps.rel_set(axis, motion_values.distance_to_move_deg, wait=True)

        yield from read_hardware_during_collection(
            composite.aperture_scatterguard,
            composite.attenuator,
            composite.flux,
            composite.dcm,
            composite.eiger,
        )

    yield from _rotation_scan_plan(motion_values, composite)


def _cleanup_plan(composite: RotationScanComposite, **kwargs):
    LOGGER.info("Cleaning up after rotation scan")
    max_vel = yield from bps.rd(composite.smargon.omega.max_velocity)
    yield from cleanup_sample_environment(composite.detector_motion, group="cleanup")
    yield from bps.abs_set(composite.smargon.omega.velocity, max_vel, group="cleanup")
    yield from make_trigger_safe(composite.zebra, group="cleanup")
    yield from bpp.finalize_wrapper(disarm_zebra(composite.zebra), bps.wait("cleanup"))


def _move_and_rotation(
    composite: RotationScanComposite,
    params: RotationScan,
    oav_params: OAVParameters,
):
    motor_time_to_speed = yield from bps.rd(composite.smargon.omega.acceleration_time)
    max_vel = yield from bps.rd(composite.smargon.omega.max_velocity)
    motion_values = calculate_motion_profile(params, motor_time_to_speed, max_vel)

    def _div_by_1000_if_not_none(num: float | None):
        return num / 1000 if num else num

    LOGGER.info("moving to position (if specified)")
    yield from move_x_y_z(
        composite.smargon,
        _div_by_1000_if_not_none(params.x_start_um),
        _div_by_1000_if_not_none(params.y_start_um),
        _div_by_1000_if_not_none(params.z_start_um),
        group=CONST.WAIT.MOVE_GONIO_TO_START,
    )
    yield from move_phi_chi_omega(
        composite.smargon,
        params.phi_start_deg,
        params.chi_start_deg,
        group=CONST.WAIT.MOVE_GONIO_TO_START,
    )
    if params.take_snapshots:
        yield from bps.wait(CONST.WAIT.MOVE_GONIO_TO_START)
        yield from setup_oav_snapshot_plan(
            composite, params, motion_values.max_velocity_deg_s
        )
        yield from oav_snapshot_plan(composite, params, oav_params)
    yield from rotation_scan_plan(
        composite,
        params,
        motion_values,
    )


def rotation_scan(
    composite: RotationScanComposite,
    parameters: RotationScan,
    oav_params: OAVParameters | None = None,
) -> MsgGenerator:
    if not oav_params:
        oav_params = OAVParameters(context="xrayCentring")

    @bpp.set_run_key_decorator("rotation_scan")
    @bpp.run_decorator(  # attach experiment metadata to the start document
        md={
            "subplan_name": CONST.PLAN.ROTATION_OUTER,
            CONST.TRIGGER.ZOCALO: CONST.PLAN.ROTATION_MAIN,
            "hyperion_parameters": parameters.json(),
            "activate_callbacks": [
                "RotationISPyBCallback",
                "RotationNexusFileCallback",
            ],
        }
    )
    def rotation_scan_plan_with_stage_and_cleanup(
        params: RotationScan,
    ):
        eiger: EigerDetector = composite.eiger
        eiger.set_detector_parameters(params.detector_params)

        @bpp.stage_decorator([eiger])
        @bpp.finalize_decorator(lambda: _cleanup_plan(composite))
        def rotation_with_cleanup_and_stage(params: RotationScan):
            assert composite.aperture_scatterguard.aperture_positions is not None
            LOGGER.info("setting up sample environment...")
            yield from begin_sample_environment_setup(
                composite.detector_motion,
                composite.attenuator,
                params.transmission_frac,
                params.detector_params.detector_distance,
            )

            yield from _move_and_rotation(composite, params, oav_params)

        LOGGER.info("setting up and staging eiger...")
        yield from rotation_with_cleanup_and_stage(params)

    yield from rotation_scan_plan_with_stage_and_cleanup(parameters)


def multi_rotation_scan(
    composite: RotationScanComposite,
    parameters: MultiRotationScan,
    oav_params: OAVParameters | None = None,
) -> MsgGenerator:
    if not oav_params:
        oav_params = OAVParameters(context="xrayCentring")
    eiger: EigerDetector = composite.eiger
    eiger.set_detector_parameters(parameters.detector_params)
    assert composite.aperture_scatterguard.aperture_positions is not None
    LOGGER.info("setting up sample environment...")
    yield from begin_sample_environment_setup(
        composite.detector_motion,
        composite.attenuator,
        parameters.transmission_frac,
        parameters.detector_params.detector_distance,
    )

    @bpp.set_run_key_decorator("multi_rotation_scan")
    @bpp.run_decorator(
        md={
            "subplan_name": CONST.PLAN.ROTATION_MULTI,
            "full_num_of_images": parameters.num_images,
            "meta_data_run_number": parameters.detector_params.run_number,
            "activate_callbacks": [
                "RotationISPyBCallback",
                "RotationNexusFileCallback",
            ],
        }
    )
    @bpp.stage_decorator([eiger])
    @bpp.finalize_decorator(lambda: _cleanup_plan(composite))
    def _multi_rotation_scan():
        for single_scan in parameters.single_rotation_scans:

            @bpp.set_run_key_decorator("rotation_scan")
            @bpp.run_decorator(  # attach experiment metadata to the start document
                md={
                    "subplan_name": CONST.PLAN.ROTATION_OUTER,
                    CONST.TRIGGER.ZOCALO: CONST.PLAN.ROTATION_MAIN,
                    "hyperion_parameters": single_scan.json(),
                }
            )
            def rotation_scan_core(
                params: RotationScan,
            ):
                yield from _move_and_rotation(composite, params, oav_params)

            yield from rotation_scan_core(single_scan)

    LOGGER.info("setting up and staging eiger...")
    yield from _multi_rotation_scan()
