from __future__ import annotations

import dataclasses
from functools import partial
from pathlib import Path
from time import time
from typing import Callable, Protocol

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import numpy as np
from attr import dataclass
from blueapi.core import BlueskyContext, MsgGenerator
from dodal.devices.aperturescatterguard import (
    ApertureScatterguard,
    SingleAperturePosition,
)
from dodal.devices.attenuator import Attenuator
from dodal.devices.backlight import Backlight
from dodal.devices.dcm import DCM
from dodal.devices.eiger import EigerDetector
from dodal.devices.fast_grid_scan import (
    FastGridScanCommon,
    PandAFastGridScan,
    ZebraFastGridScan,
)
from dodal.devices.fast_grid_scan import (
    set_fast_grid_scan_params as set_flyscan_params,
)
from dodal.devices.flux import Flux
from dodal.devices.robot import BartRobot
from dodal.devices.s4_slit_gaps import S4SlitGaps
from dodal.devices.smargon import Smargon, StubPosition
from dodal.devices.synchrotron import Synchrotron
from dodal.devices.undulator import Undulator
from dodal.devices.xbpm_feedback import XBPMFeedback
from dodal.devices.zebra import Zebra
from dodal.devices.zocalo import (
    get_processing_result,
)
from dodal.devices.zocalo.zocalo_results import (
    ZOCALO_READING_PLAN_NAME,
    ZOCALO_STAGE_GROUP,
    ZocaloResults,
    get_processing_result,
)
from dodal.plans.check_topup import check_topup_and_wait_if_necessary
from mx_bluesky.device_setup_plans.read_hardware_for_setup import (
    read_hardware_for_zocalo,
)
from ophyd_async.panda import HDFPanda
from scanspec.core import AxesPoints, Axis

from hyperion.device_setup_plans.manipulate_sample import move_x_y_z
from hyperion.device_setup_plans.read_hardware_for_setup import (
    read_hardware_during_collection,
    read_hardware_pre_collection,
)
from hyperion.device_setup_plans.setup_panda import (
    disarm_panda_for_gridscan,
    set_panda_directory,
    setup_panda_for_flyscan,
)
from hyperion.device_setup_plans.setup_zebra import (
    set_zebra_shutter_to_manual,
    setup_zebra_for_gridscan,
    setup_zebra_for_panda_flyscan,
)
from hyperion.device_setup_plans.xbpm_feedback import (
    transmission_and_xbpm_feedback_for_collection_decorator,
)
from hyperion.exceptions import WarningException
from hyperion.log import LOGGER
from hyperion.parameters.constants import CONST
from hyperion.parameters.gridscan import ThreeDGridScan
from hyperion.tracing import TRACER
from hyperion.utils.aperturescatterguard import (
    load_default_aperture_scatterguard_positions_if_unset,
)
from hyperion.utils.context import device_composite_from_context


class SmargonSpeedException(Exception):
    pass


@dataclasses.dataclass
class FlyScanXRayCentreComposite:
    """All devices which are directly or indirectly required by this plan"""

    aperture_scatterguard: ApertureScatterguard
    attenuator: Attenuator
    backlight: Backlight
    dcm: DCM
    eiger: EigerDetector
    zebra_fast_grid_scan: ZebraFastGridScan
    flux: Flux
    s4_slit_gaps: S4SlitGaps
    smargon: Smargon
    undulator: Undulator
    synchrotron: Synchrotron
    xbpm_feedback: XBPMFeedback
    zebra: Zebra
    zocalo: ZocaloResults
    panda: HDFPanda
    panda_fast_grid_scan: PandAFastGridScan
    robot: BartRobot

    @property
    def sample_motors(self) -> Smargon:
        """Convenience alias with a more user-friendly name"""
        return self.smargon

    def __post_init__(self):
        """Ensure that aperture positions are loaded whenever this class is created."""
        load_default_aperture_scatterguard_positions_if_unset(
            self.aperture_scatterguard
        )


def create_devices(context: BlueskyContext) -> FlyScanXRayCentreComposite:
    """Creates the devices required for the plan and connect to them"""
    return device_composite_from_context(context, FlyScanXRayCentreComposite)


def flyscan_xray_centre(
    composite: FlyScanXRayCentreComposite,
    parameters: ThreeDGridScan,
) -> MsgGenerator:
    """Create the plan to run the grid scan based on provided parameters.

    The ispyb handler should be added to the whole gridscan as we want to capture errors
    at any point in it.

    Args:
        parameters (ThreeDGridScan): The parameters to run the scan.

    Returns:
        Generator: The plan for the gridscan
    """
    parameters.features.update_self_from_server()
    composite.eiger.set_detector_parameters(parameters.detector_params)
    composite.zocalo.zocalo_environment = parameters.zocalo_environment

    feature_controlled = _get_feature_controlled(composite, parameters)

    @bpp.set_run_key_decorator(CONST.PLAN.GRIDSCAN_OUTER)
    @bpp.run_decorator(  # attach experiment metadata to the start document
        md={
            "subplan_name": CONST.PLAN.GRIDSCAN_OUTER,
            CONST.TRIGGER.ZOCALO: CONST.PLAN.DO_FGS,
            "zocalo_environment": parameters.zocalo_environment,
            "hyperion_parameters": parameters.json(),
            "activate_callbacks": [
                "GridscanNexusFileCallback",
            ],
        }
    )
    @bpp.finalize_decorator(lambda: feature_controlled.tidy_plan(composite))
    @transmission_and_xbpm_feedback_for_collection_decorator(
        composite.xbpm_feedback,
        composite.attenuator,
        parameters.transmission_frac,
    )
    def run_gridscan_and_move_and_tidy(
        fgs_composite: FlyScanXRayCentreComposite,
        params: ThreeDGridScan,
        feature_controlled: _FeatureControlled,
    ):
        yield from run_gridscan_and_move(fgs_composite, params, feature_controlled)

    return run_gridscan_and_move_and_tidy(composite, parameters, feature_controlled)


@bpp.set_run_key_decorator(CONST.PLAN.GRIDSCAN_AND_MOVE)
@bpp.run_decorator(md={"subplan_name": CONST.PLAN.GRIDSCAN_AND_MOVE})
def run_gridscan_and_move(
    fgs_composite: FlyScanXRayCentreComposite,
    parameters: ThreeDGridScan,
    feature_controlled: _FeatureControlled,
) -> MsgGenerator:
    """A multi-run plan which runs a gridscan, gets the results from zocalo
    and moves to the centre of mass determined by zocalo"""

    # We get the initial motor positions so we can return to them on zocalo failure
    initial_xyz = np.array(
        [
            (yield from bps.rd(fgs_composite.sample_motors.x)),
            (yield from bps.rd(fgs_composite.sample_motors.y)),
            (yield from bps.rd(fgs_composite.sample_motors.z)),
        ]
    )

    yield from feature_controlled.setup_trigger(fgs_composite, parameters, initial_xyz)

    LOGGER.info("Starting grid scan")
    yield from bps.stage(
        fgs_composite.zocalo, group=ZOCALO_STAGE_GROUP
    )  # connect to zocalo and make sure the queue is clear
    yield from run_gridscan(fgs_composite, parameters, feature_controlled)

    LOGGER.info("Grid scan finished, getting results.")

    with TRACER.start_span("wait_for_zocalo"):
        yield from bps.trigger_and_read(
            [fgs_composite.zocalo], name=ZOCALO_READING_PLAN_NAME
        )
        LOGGER.info("Zocalo triggered and read, interpreting results.")
        xray_centre, bbox_size = yield from get_processing_result(fgs_composite.zocalo)
        LOGGER.info(f"Got xray centre: {xray_centre}, bbox size: {bbox_size}")
        if xray_centre is not None:
            xray_centre = parameters.FGS_params.grid_position_to_motor_position(
                xray_centre
            )
        else:
            xray_centre = initial_xyz
            LOGGER.warning("No X-ray centre recieved")
        if bbox_size is not None:
            with TRACER.start_span("change_aperture"):
                yield from set_aperture_for_bbox_size(
                    fgs_composite.aperture_scatterguard, bbox_size
                )
        else:
            LOGGER.warning("No bounding box size recieved")

    # once we have the results, go to the appropriate position
    LOGGER.info("Moving to centre of mass.")
    with TRACER.start_span("move_to_result"):
        yield from move_x_y_z(fgs_composite.sample_motors, *xray_centre, wait=True)

    if parameters.FGS_params.set_stub_offsets:
        LOGGER.info("Recentring smargon co-ordinate system to this point.")
        yield from bps.mv(
            fgs_composite.sample_motors.stub_offsets, StubPosition.CURRENT_AS_CENTER
        )

    # Turn off dev/shm streaming to avoid filling disk, see https://github.com/DiamondLightSource/hyperion/issues/1395
    LOGGER.info("Turning off Eiger dev/shm streaming")
    yield from bps.abs_set(fgs_composite.eiger.odin.fan.dev_shm_enable, 0)

    # Wait on everything before returning to GDA (particularly apertures), can be removed
    # when we do not return to GDA here
    yield from bps.wait()


@bpp.set_run_key_decorator(CONST.PLAN.GRIDSCAN_MAIN)
@bpp.run_decorator(md={"subplan_name": CONST.PLAN.GRIDSCAN_MAIN})
def run_gridscan(
    fgs_composite: FlyScanXRayCentreComposite,
    parameters: ThreeDGridScan,
    feature_controlled: _FeatureControlled,
    md={
        "plan_name": CONST.PLAN.GRIDSCAN_MAIN,
    },
):
    sample_motors = fgs_composite.sample_motors

    # Currently gridscan only works for omega 0, see #
    with TRACER.start_span("moving_omega_to_0"):
        yield from bps.abs_set(sample_motors.omega, 0)

    # We only subscribe to the communicator callback for run_gridscan, so this is where
    # we should generate an event reading the values which need to be included in the
    # ispyb deposition
    with TRACER.start_span("ispyb_hardware_readings"):
        yield from read_hardware_pre_collection(
            fgs_composite.undulator,
            fgs_composite.synchrotron,
            fgs_composite.s4_slit_gaps,
            fgs_composite.robot,
            fgs_composite.smargon,
        )

    read_during_collection = partial(
        read_hardware_during_collection,
        fgs_composite.aperture_scatterguard,
        fgs_composite.attenuator,
        fgs_composite.flux,
        fgs_composite.dcm,
        fgs_composite.eiger,
    )

    LOGGER.info("Setting fgs params")
    yield from feature_controlled.set_flyscan_params()

    LOGGER.info("Waiting for gridscan validity check")
    yield from wait_for_gridscan_valid(feature_controlled.fgs_motors)

    LOGGER.info("Waiting for arming to finish")
    yield from bps.wait(CONST.WAIT.GRID_READY_FOR_DC)
    yield from bps.stage(fgs_composite.eiger)

    yield from kickoff_and_complete_gridscan(
        feature_controlled.fgs_motors,
        fgs_composite.eiger,
        fgs_composite.synchrotron,
        [parameters.scan_points_first_grid, parameters.scan_points_second_grid],
        parameters.scan_indices,
        do_during_run=read_during_collection,
    )
    yield from bps.abs_set(feature_controlled.fgs_motors.z_steps, 0, wait=False)


def kickoff_and_complete_gridscan(
    gridscan: FastGridScanCommon,
    eiger: EigerDetector,
    synchrotron: Synchrotron,
    scan_points: list[AxesPoints[Axis]],
    scan_start_indices: list[int],
    do_during_run: Callable[[], MsgGenerator] | None = None,
):
    @TRACER.start_as_current_span(CONST.PLAN.DO_FGS)
    @bpp.set_run_key_decorator(CONST.PLAN.DO_FGS)
    @bpp.run_decorator(
        md={
            "subplan_name": CONST.PLAN.DO_FGS,
            "scan_points": scan_points,
            "scan_start_indices": scan_start_indices,
        }
    )
    @bpp.contingency_decorator(
        except_plan=lambda e: (yield from bps.stop(eiger)),
        else_plan=lambda: (yield from bps.unstage(eiger)),
    )
    def do_fgs():
        # Check topup gate
        expected_images = yield from bps.rd(gridscan.expected_images)
        exposure_sec_per_image = yield from bps.rd(eiger.cam.acquire_time)
        LOGGER.info("waiting for topup if necessary...")
        yield from check_topup_and_wait_if_necessary(
            synchrotron,
            expected_images * exposure_sec_per_image,
            30.0,
        )
        yield from read_hardware_for_zocalo(eiger)
        LOGGER.info("Wait for all moves with no assigned group")
        yield from bps.wait()
        LOGGER.info("kicking off FGS")
        yield from bps.kickoff(gridscan, wait=True)
        gridscan_start_time = time()
        LOGGER.info("Waiting for Zocalo device queue to have been cleared...")
        yield from bps.wait(
            ZOCALO_STAGE_GROUP
        )  # Make sure ZocaloResults queue is clear and ready to accept our new data
        if do_during_run:
            LOGGER.info(f"Running {do_during_run} during FGS")
            yield from do_during_run()
        LOGGER.info("completing FGS")
        yield from bps.complete(gridscan, wait=True)

        # Remove this logging statement once metrics have been added
        LOGGER.info(
            f"Gridscan motion program took {round(time()-gridscan_start_time,2)} to complete"
        )

    yield from do_fgs()


def wait_for_gridscan_valid(fgs_motors: FastGridScanCommon, timeout=0.5):
    LOGGER.info("Waiting for valid fgs_params")
    SLEEP_PER_CHECK = 0.1
    times_to_check = int(timeout / SLEEP_PER_CHECK)
    for _ in range(times_to_check):
        scan_invalid = yield from bps.rd(fgs_motors.scan_invalid)
        pos_counter = yield from bps.rd(fgs_motors.position_counter)
        LOGGER.debug(
            f"Scan invalid: {scan_invalid} and position counter: {pos_counter}"
        )
        if not scan_invalid and pos_counter == 0:
            LOGGER.info("Gridscan scan valid and position counter reset")
            return
        yield from bps.sleep(SLEEP_PER_CHECK)
    raise WarningException("Scan invalid - pin too long/short/bent and out of range")


def set_aperture_for_bbox_size(
    aperture_device: ApertureScatterguard,
    bbox_size: list[int] | np.ndarray,
):
    # bbox_size is [x,y,z], for i03 we only care about x
    assert aperture_device.aperture_positions is not None

    new_selected_aperture: SingleAperturePosition = (
        aperture_device.aperture_positions.MEDIUM
        if bbox_size[0] < 2
        else aperture_device.aperture_positions.LARGE
    )
    LOGGER.info(
        f"Setting aperture to {new_selected_aperture} based on bounding box size {bbox_size}."
    )

    @bpp.set_run_key_decorator("change_aperture")
    @bpp.run_decorator(
        md={
            "subplan_name": "change_aperture",
            "aperture_size": new_selected_aperture.GDA_name,
        }
    )
    def set_aperture():
        yield from bps.abs_set(aperture_device, new_selected_aperture)

    yield from set_aperture()


@dataclass
class _FeatureControlled:
    class _ZebraSetup(Protocol):
        def __call__(
            self, zebra: Zebra, group="setup_zebra_for_gridscan", wait=True
        ) -> MsgGenerator: ...

    class _ExtraSetup(Protocol):
        def __call__(
            self,
            fgs_composite: FlyScanXRayCentreComposite,
            parameters: ThreeDGridScan,
            initial_xyz: np.ndarray,
        ) -> MsgGenerator: ...

    setup_trigger: _ExtraSetup
    tidy_plan: Callable[[FlyScanXRayCentreComposite], MsgGenerator]
    set_flyscan_params: Callable[[], MsgGenerator]
    fgs_motors: FastGridScanCommon


def _get_feature_controlled(
    fgs_composite: FlyScanXRayCentreComposite,
    parameters: ThreeDGridScan,
):
    if parameters.features.use_panda_for_gridscan:
        return _FeatureControlled(
            setup_trigger=_panda_triggering_setup,
            tidy_plan=_panda_tidy,
            set_flyscan_params=partial(
                set_flyscan_params,
                fgs_composite.panda_fast_grid_scan,
                parameters.panda_FGS_params,
            ),
            fgs_motors=fgs_composite.panda_fast_grid_scan,
        )
    else:
        return _FeatureControlled(
            setup_trigger=_zebra_triggering_setup,
            tidy_plan=partial(_generic_tidy, group="flyscan_zebra_tidy", wait=True),
            set_flyscan_params=partial(
                set_flyscan_params,
                fgs_composite.zebra_fast_grid_scan,
                parameters.FGS_params,
            ),
            fgs_motors=fgs_composite.zebra_fast_grid_scan,
        )


def _generic_tidy(
    fgs_composite: FlyScanXRayCentreComposite, group, wait=True
) -> MsgGenerator:
    LOGGER.info("Tidying up Zebra")
    yield from set_zebra_shutter_to_manual(fgs_composite.zebra, group=group, wait=wait)
    LOGGER.info("Tidying up Zocalo")
    # make sure we don't consume any other results
    yield from bps.unstage(fgs_composite.zocalo, group=group, wait=wait)


def _panda_tidy(fgs_composite: FlyScanXRayCentreComposite):
    group = "panda_flyscan_tidy"
    LOGGER.info("Disabling panda blocks")
    yield from disarm_panda_for_gridscan(fgs_composite.panda, group)
    yield from _generic_tidy(fgs_composite, group, False)
    yield from bps.wait(group, timeout=10)
    yield from bps.unstage(fgs_composite.panda)


def _zebra_triggering_setup(
    fgs_composite: FlyScanXRayCentreComposite,
    parameters: ThreeDGridScan,
    initial_xyz: np.ndarray,
):
    yield from setup_zebra_for_gridscan(fgs_composite.zebra, wait=True)


def _panda_triggering_setup(
    fgs_composite: FlyScanXRayCentreComposite,
    parameters: ThreeDGridScan,
    initial_xyz: np.ndarray,
):
    LOGGER.info("Setting up Panda for flyscan")

    run_up_distance_mm = yield from bps.rd(
        fgs_composite.panda_fast_grid_scan.run_up_distance_mm
    )

    # Set the time between x steps pv
    DEADTIME_S = 1e-6  # according to https://www.dectris.com/en/detectors/x-ray-detectors/eiger2/eiger2-for-synchrotrons/eiger2-x/

    time_between_x_steps_ms = (DEADTIME_S + parameters.exposure_time_s) * 1e3

    smargon_speed_limit_mm_per_s = yield from bps.rd(
        fgs_composite.smargon.x.max_velocity
    )

    sample_velocity_mm_per_s = (
        parameters.panda_FGS_params.x_step_size * 1e3 / time_between_x_steps_ms
    )
    if sample_velocity_mm_per_s > smargon_speed_limit_mm_per_s:
        raise SmargonSpeedException(
            f"Smargon speed was calculated from x step size\
            {parameters.panda_FGS_params.x_step_size} and\
            time_between_x_steps_ms {time_between_x_steps_ms} as\
            {sample_velocity_mm_per_s}. The smargon's speed limit is\
            {smargon_speed_limit_mm_per_s} mm/s."
        )
    else:
        LOGGER.info(
            f"Panda grid scan: Smargon speed set to {smargon_speed_limit_mm_per_s} mm/s"
            f" and using a run-up distance of {run_up_distance_mm}"
        )

    yield from bps.mv(
        fgs_composite.panda_fast_grid_scan.time_between_x_steps_ms,
        time_between_x_steps_ms,
    )

    directory_provider_root = Path(parameters.storage_directory)
    yield from set_panda_directory(directory_provider_root)

    yield from setup_panda_for_flyscan(
        fgs_composite.panda,
        parameters.panda_FGS_params,
        initial_xyz[0],
        parameters.exposure_time_s,
        time_between_x_steps_ms,
        sample_velocity_mm_per_s,
    )

    LOGGER.info("Setting up Zebra for panda flyscan")
    yield from setup_zebra_for_panda_flyscan(fgs_composite.zebra, wait=True)
