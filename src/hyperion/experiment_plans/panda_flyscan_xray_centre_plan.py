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
from dodal.devices.flux import Flux
from dodal.devices.panda_fast_grid_scan import PandAFastGridScan
from dodal.devices.panda_fast_grid_scan import (
    set_fast_grid_scan_params as set_flyscan_params,
)
from dodal.devices.s4_slit_gaps import S4SlitGaps
from dodal.devices.smargon import Smargon
from dodal.devices.synchrotron import Synchrotron
from dodal.devices.undulator import Undulator
from dodal.devices.xbpm_feedback import XBPMFeedback
from ophyd_async.panda import PandA

import hyperion.log
from hyperion.device_setup_plans.check_topup import check_topup_and_wait_if_necessary
from hyperion.device_setup_plans.manipulate_sample import move_x_y_z
from hyperion.device_setup_plans.read_hardware_for_setup import (
    read_hardware_for_ispyb_during_collection,
    read_hardware_for_ispyb_pre_collection,
)
from hyperion.device_setup_plans.setup_panda import (
    setup_panda_for_flyscan,
    setup_panda_shutter_to_manual,
)
from hyperion.device_setup_plans.xbpm_feedback import (
    transmission_and_xbpm_feedback_for_collection_decorator,
)
from hyperion.exceptions import WarningException
from hyperion.external_interaction.callbacks.xray_centre.callback_collection import (
    XrayCentreCallbackCollection,
)
from hyperion.parameters import external_parameters
from hyperion.parameters.constants import SIM_BEAMLINE
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
class PandAFlyScanXRayCentreComposite:
    """All devices which are directly or indirectly required by this plan"""

    aperture_scatterguard: ApertureScatterguard
    attenuator: Attenuator
    backlight: Backlight
    eiger: EigerDetector
    panda_fast_grid_scan: PandAFastGridScan
    flux: Flux
    s4_slit_gaps: S4SlitGaps
    smargon: Smargon
    undulator: Undulator
    synchrotron: Synchrotron
    xbpm_feedback: XBPMFeedback
    panda: PandA

    @property
    def sample_motors(self) -> Smargon:
        """Convenience alias with a more user-friendly name"""
        return self.smargon

    def __post_init__(self):
        """Ensure that aperture positions are loaded whenever this class is created."""
        load_default_aperture_scatterguard_positions_if_unset(
            self.aperture_scatterguard
        )


def create_devices(context: BlueskyContext) -> PandAFlyScanXRayCentreComposite:
    """Creates the devices required for the plan and connect to them"""
    return device_composite_from_context(context, PandAFlyScanXRayCentreComposite)


def set_aperture_for_bbox_size(
    aperture_device: ApertureScatterguard,
    bbox_size: list[int],
):
    # bbox_size is [x,y,z], for i03 we only care about x
    if bbox_size[0] < 2:
        aperture_size_positions = aperture_device.aperture_positions.MEDIUM
        selected_aperture = "MEDIUM_APERTURE"
    else:
        aperture_size_positions = aperture_device.aperture_positions.LARGE
        selected_aperture = "LARGE_APERTURE"
    hyperion.log.LOGGER.info(
        f"Setting aperture to {selected_aperture} ({aperture_size_positions}) based on bounding box size {bbox_size}."
    )

    @bpp.set_run_key_decorator("change_aperture")
    @bpp.run_decorator(
        md={"subplan_name": "change_aperture", "aperture_size": selected_aperture}
    )
    def set_aperture():
        yield from bps.abs_set(aperture_device, aperture_size_positions)

    yield from set_aperture()


def wait_for_gridscan_valid(panda_fgs_motors: PandAFastGridScan, timeout=0.5):
    hyperion.log.LOGGER.info("Waiting for valid fgs_params")
    SLEEP_PER_CHECK = 0.1
    times_to_check = int(timeout / SLEEP_PER_CHECK)
    for _ in range(times_to_check):
        scan_invalid = yield from bps.rd(panda_fgs_motors.scan_invalid)
        pos_counter = yield from bps.rd(panda_fgs_motors.position_counter)
        hyperion.log.LOGGER.debug(
            f"Scan invalid: {scan_invalid} and position counter: {pos_counter}"
        )
        if not scan_invalid and pos_counter == 0:
            hyperion.log.LOGGER.info("Gridscan scan valid and position counter reset")
            return
        yield from bps.sleep(SLEEP_PER_CHECK)
    raise WarningException("Scan invalid - pin too long/short/bent and out of range")


def tidy_up_plans(fgs_composite: PandAFlyScanXRayCentreComposite):
    hyperion.log.LOGGER.info("Tidying up PandA")
    yield from setup_panda_shutter_to_manual(fgs_composite.panda)


@bpp.set_run_key_decorator("run_gridscan")
@bpp.run_decorator(md={"subplan_name": "run_gridscan"})
def run_gridscan(
    fgs_composite: PandAFlyScanXRayCentreComposite,
    parameters: GridscanInternalParameters,
    md={
        "plan_name": "run_gridscan",
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

    hyperion.log.LOGGER.info("Setting fgs params")
    yield from set_flyscan_params(fgs_motors, parameters.experiment_params)

    yield from wait_for_gridscan_valid(fgs_motors)

    @bpp.set_run_key_decorator("do_fgs")
    @bpp.run_decorator(md={"subplan_name": "do_fgs"})
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

    hyperion.log.LOGGER.info("Waiting for arming to finish")
    yield from bps.wait("ready_for_data_collection")
    yield from bps.stage(fgs_composite.eiger)

    with TRACER.start_span("do_fgs"):
        yield from do_fgs()

    yield from bps.abs_set(fgs_motors.z_steps, 0, wait=False)


@bpp.set_run_key_decorator("run_gridscan_and_move")
@bpp.run_decorator(md={"subplan_name": "run_gridscan_and_move"})
def run_gridscan_and_move(
    fgs_composite: PandAFlyScanXRayCentreComposite,
    parameters: GridscanInternalParameters,
    subscriptions: XrayCentreCallbackCollection,
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

    yield from setup_panda_for_flyscan(fgs_composite.panda)

    hyperion.log.LOGGER.info("Starting grid scan")

    yield from run_gridscan(fgs_composite, parameters)

    # the data were submitted to zocalo by the zocalo callback during the gridscan,
    # but results may not be ready, and need to be collected regardless.
    # it might not be ideal to block for this, see #327
    xray_centre, bbox_size = subscriptions.zocalo_handler.wait_for_results(initial_xyz)

    if bbox_size is not None:
        with TRACER.start_span("change_aperture"):
            yield from set_aperture_for_bbox_size(
                fgs_composite.aperture_scatterguard, bbox_size
            )

    # once we have the results, go to the appropriate position
    hyperion.log.LOGGER.info("Moving to centre of mass.")
    with TRACER.start_span("move_to_result"):
        yield from move_x_y_z(fgs_composite.sample_motors, *xray_centre, wait=True)


def flyscan_xray_centre(
    composite: PandAFlyScanXRayCentreComposite,
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

    subscriptions = XrayCentreCallbackCollection.from_params(parameters)

    @bpp.subs_decorator(  # subscribe the RE to nexus, ispyb, and zocalo callbacks
        list(subscriptions)  # must be the outermost decorator to receive the metadata
    )
    @bpp.set_run_key_decorator("run_gridscan_move_and_tidy")
    @bpp.run_decorator(  # attach experiment metadata to the start document
        md={
            "subplan_name": "run_gridscan_move_and_tidy",
            "hyperion_internal_parameters": parameters.json(),
        }
    )
    @bpp.finalize_decorator(lambda: tidy_up_plans(composite))
    @transmission_and_xbpm_feedback_for_collection_decorator(
        composite.xbpm_feedback,
        composite.attenuator,
        parameters.hyperion_params.ispyb_params.transmission_fraction,
    )
    def run_gridscan_and_move_and_tidy(fgs_composite, params, comms):
        yield from run_gridscan_and_move(fgs_composite, params, comms)

    return run_gridscan_and_move_and_tidy(composite, parameters, subscriptions)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--beamline",
        help="The beamline prefix this is being run on",
        default=SIM_BEAMLINE,
    )
    args = parser.parse_args()

    RE = RunEngine({})
    RE.waiting_hook = ProgressBarManager()
    from hyperion.parameters.plan_specific.gridscan_internal_params import (
        GridscanInternalParameters,
    )

    parameters = GridscanInternalParameters(**external_parameters.from_file())
    subscriptions = XrayCentreCallbackCollection.from_params(parameters)

    context = setup_context(wait_for_connection=True)
    composite = create_devices(context)

    RE(flyscan_xray_centre(composite, parameters))
