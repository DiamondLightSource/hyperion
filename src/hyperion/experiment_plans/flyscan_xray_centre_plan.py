from __future__ import annotations

import argparse
import dataclasses
from typing import TYPE_CHECKING, Any

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import numpy as np
from blueapi.core import BlueskyContext, MsgGenerator
from bluesky.run_engine import RunEngine
from bluesky.utils import ProgressBarManager
from dodal.devices.aperturescatterguard import ApertureScatterguard
from dodal.devices.attenuator import Attenuator
from dodal.devices.backlight import Backlight
from dodal.devices.eiger import EigerDetector
from dodal.devices.fast_grid_scan import FastGridScan
from dodal.devices.fast_grid_scan import set_fast_grid_scan_params as set_flyscan_params
from dodal.devices.flux import Flux
from dodal.devices.s4_slit_gaps import S4SlitGaps
from dodal.devices.smargon import Smargon, StubPosition
from dodal.devices.synchrotron import Synchrotron
from dodal.devices.undulator import Undulator
from dodal.devices.xbpm_feedback import XBPMFeedback
from dodal.devices.zebra import Zebra
from dodal.devices.zocalo import (
    ZOCALO_READING_PLAN_NAME,
    ZocaloResults,
    get_processing_result,
)

from hyperion.device_setup_plans.check_topup import check_topup_and_wait_if_necessary
from hyperion.device_setup_plans.manipulate_sample import move_x_y_z
from hyperion.device_setup_plans.read_hardware_for_setup import (
    read_hardware_for_ispyb_during_collection,
    read_hardware_for_ispyb_pre_collection,
)
from hyperion.device_setup_plans.setup_zebra import (
    set_zebra_shutter_to_manual,
    setup_zebra_for_gridscan,
)
from hyperion.device_setup_plans.xbpm_feedback import (
    transmission_and_xbpm_feedback_for_collection_decorator,
)
from hyperion.exceptions import WarningException
from hyperion.external_interaction.callbacks.xray_centre.callback_collection import (
    XrayCentreCallbackCollection,
)
from hyperion.log import LOGGER
from hyperion.parameters import external_parameters
from hyperion.parameters.constants import (
    DO_FGS,
    GRIDSCAN_AND_MOVE,
    GRIDSCAN_MAIN_PLAN,
    GRIDSCAN_OUTER_PLAN,
    SIM_BEAMLINE,
)
from hyperion.tracing import TRACER
from hyperion.utils.aperturescatterguard import (
    load_default_aperture_scatterguard_positions_if_unset,
)
from hyperion.utils.context import device_composite_from_context, setup_context

if TYPE_CHECKING:
    from hyperion.parameters.plan_specific.gridscan_internal_params import (
        GridscanInternalParameters,
    )


@dataclasses.dataclass
class FlyScanXRayCentreComposite:
    """All devices which are directly or indirectly required by this plan"""

    aperture_scatterguard: ApertureScatterguard
    attenuator: Attenuator
    backlight: Backlight
    eiger: EigerDetector
    fast_grid_scan: FastGridScan
    flux: Flux
    s4_slit_gaps: S4SlitGaps
    smargon: Smargon
    undulator: Undulator
    synchrotron: Synchrotron
    xbpm_feedback: XBPMFeedback
    zebra: Zebra
    zocalo: ZocaloResults

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


def set_aperture_for_bbox_size(
    aperture_device: ApertureScatterguard,
    bbox_size: list[int] | np.ndarray,
):
    # bbox_size is [x,y,z], for i03 we only care about x
    assert aperture_device.aperture_positions is not None
    if bbox_size[0] < 2:
        aperture_size_positions = aperture_device.aperture_positions.MEDIUM
        selected_aperture = "MEDIUM_APERTURE"
    else:
        aperture_size_positions = aperture_device.aperture_positions.LARGE
        selected_aperture = "LARGE_APERTURE"
    LOGGER.info(
        f"Setting aperture to {selected_aperture} ({aperture_size_positions}) based on bounding box size {bbox_size}."
    )

    @bpp.set_run_key_decorator("change_aperture")
    @bpp.run_decorator(
        md={"subplan_name": "change_aperture", "aperture_size": selected_aperture}
    )
    def set_aperture():
        yield from bps.abs_set(aperture_device, aperture_size_positions)

    yield from set_aperture()


def wait_for_gridscan_valid(fgs_motors: FastGridScan, timeout=0.5):
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


def tidy_up_plans(fgs_composite: FlyScanXRayCentreComposite):
    LOGGER.info("Tidying up Zebra")
    yield from set_zebra_shutter_to_manual(fgs_composite.zebra)


@bpp.set_run_key_decorator(GRIDSCAN_MAIN_PLAN)
@bpp.run_decorator(md={"subplan_name": GRIDSCAN_MAIN_PLAN})
def run_gridscan(
    fgs_composite: FlyScanXRayCentreComposite,
    parameters: GridscanInternalParameters,
    md={
        "plan_name": GRIDSCAN_MAIN_PLAN,
    },
):
    yield from bps.stage(fgs_composite.zocalo)  # clear any stale processing results
    sample_motors = fgs_composite.sample_motors

    # Currently gridscan only works for omega 0, see #
    with TRACER.start_span("moving_omega_to_0"):
        yield from bps.abs_set(sample_motors.omega, 0)

    # We only subscribe to the communicator callback for run_gridscan, so this is where
    # we should generate an event reading the values which need to be included in the
    # ispyb deposition
    with TRACER.start_span("ispyb_hardware_readings"):
        yield from read_hardware_for_ispyb_pre_collection(
            fgs_composite.undulator,
            fgs_composite.synchrotron,
            fgs_composite.s4_slit_gaps,
        )
        yield from read_hardware_for_ispyb_during_collection(
            fgs_composite.attenuator,
            fgs_composite.flux,
        )

    fgs_motors = fgs_composite.fast_grid_scan

    LOGGER.info("Setting fgs params")
    yield from set_flyscan_params(fgs_motors, parameters.experiment_params)

    yield from wait_for_gridscan_valid(fgs_motors)

    @bpp.set_run_key_decorator(DO_FGS)
    @bpp.run_decorator(md={"subplan_name": DO_FGS})
    @bpp.contingency_decorator(
        except_plan=lambda e: (yield from bps.stop(fgs_composite.eiger)),
        else_plan=lambda: (yield from bps.unstage(fgs_composite.eiger)),
    )
    def do_fgs():
        yield from bps.wait()  # Wait for all moves to complete
        # Check topup gate
        dwell_time_in_s = parameters.experiment_params.dwell_time_ms / 1000.0
        total_exposure = (
            parameters.experiment_params.get_num_images() * dwell_time_in_s
        )  # Expected exposure time for full scan
        yield from check_topup_and_wait_if_necessary(
            fgs_composite.synchrotron,
            total_exposure,
            30.0,
        )
        yield from bps.kickoff(fgs_motors)
        yield from bps.complete(fgs_motors, wait=True)

    LOGGER.info("Waiting for arming to finish")
    yield from bps.wait("ready_for_data_collection")
    yield from bps.stage(fgs_composite.eiger)

    with TRACER.start_span("do_fgs"):
        yield from do_fgs()

    yield from bps.abs_set(fgs_motors.z_steps, 0, wait=False)


@bpp.set_run_key_decorator(GRIDSCAN_AND_MOVE)
@bpp.run_decorator(md={"subplan_name": GRIDSCAN_AND_MOVE})
def run_gridscan_and_move(
    fgs_composite: FlyScanXRayCentreComposite,
    parameters: GridscanInternalParameters,
):
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

    yield from setup_zebra_for_gridscan(fgs_composite.zebra)

    LOGGER.info("Starting grid scan")

    yield from run_gridscan(fgs_composite, parameters)

    LOGGER.info("Grid scan finished, getting results.")

    with TRACER.start_span("wait_for_zocalo"):
        yield from bps.trigger_and_read(
            [fgs_composite.zocalo], name=ZOCALO_READING_PLAN_NAME
        )
        LOGGER.info("Zocalo triggered and read, interpreting results.")
        xray_centre, bbox_size = yield from get_processing_result(fgs_composite.zocalo)
        LOGGER.info(f"Got xray centre: {xray_centre}, bbox size: {bbox_size}")
        if xray_centre is not None:
            xray_centre = parameters.experiment_params.grid_position_to_motor_position(
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

    if parameters.experiment_params.set_stub_offsets:
        LOGGER.info("Recentring smargon co-ordinate system to this point.")
        yield from bps.mv(
            fgs_composite.sample_motors.stub_offsets, StubPosition.CURRENT_AS_CENTER
        )


def flyscan_xray_centre(
    composite: FlyScanXRayCentreComposite,
    parameters: Any,
) -> MsgGenerator:
    """Create the plan to run the grid scan based on provided parameters.

    The ispyb handler should be added to the whole gridscan as we want to capture errors
    at any point in it.

    Args:
        parameters (FGSInternalParameters): The parameters to run the scan.

    Returns:
        Generator: The plan for the gridscan
    """
    composite.eiger.set_detector_parameters(parameters.hyperion_params.detector_params)
    composite.zocalo.zocalo_environment = parameters.hyperion_params.zocalo_environment

    @bpp.set_run_key_decorator(GRIDSCAN_OUTER_PLAN)
    @bpp.run_decorator(  # attach experiment metadata to the start document
        md={
            "subplan_name": GRIDSCAN_OUTER_PLAN,
            "hyperion_internal_parameters": parameters.json(),
            "activate_callbacks": [
                "XrayCentreZocaloCallback",
                "GridscanISPyBCallback",
                "GridscanNexusFileCallback",
            ],
        }
    )
    @bpp.finalize_decorator(lambda: tidy_up_plans(composite))
    @transmission_and_xbpm_feedback_for_collection_decorator(
        composite.xbpm_feedback,
        composite.attenuator,
        parameters.hyperion_params.ispyb_params.transmission_fraction,
    )
    def run_gridscan_and_move_and_tidy(fgs_composite, params):
        yield from run_gridscan_and_move(fgs_composite, params)

    return run_gridscan_and_move_and_tidy(composite, parameters)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--beamline",
        help="The beamline prefix this is being run on",
        default=SIM_BEAMLINE,
    )
    args = parser.parse_args()

    RE = RunEngine({})
    RE.waiting_hook = ProgressBarManager()  # type: ignore
    from hyperion.parameters.plan_specific.gridscan_internal_params import (
        GridscanInternalParameters,
    )

    parameters = GridscanInternalParameters(**external_parameters.from_file())
    subscriptions = XrayCentreCallbackCollection.setup()

    context = setup_context(wait_for_connection=True)
    composite = create_devices(context)

    RE(flyscan_xray_centre(composite, parameters))
