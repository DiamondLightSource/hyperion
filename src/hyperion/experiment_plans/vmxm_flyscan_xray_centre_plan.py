from __future__ import annotations

import argparse
import dataclasses
from typing import TYPE_CHECKING, Any

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import numpy as np
from blueapi.core import BlueskyContext, MsgGenerator
from bluesky.preprocessors import finalize_wrapper, make_decorator
from bluesky.run_engine import RunEngine
from bluesky.utils import ProgressBarManager
from dodal.devices.backlight import Backlight
from dodal.devices.eiger import EigerDetector
from dodal.devices.fast_grid_scan import FastGridScan
from dodal.devices.fast_grid_scan import set_fast_grid_scan_params as set_flyscan_params
from dodal.devices.smargon import Smargon
from dodal.devices.synchrotron import Synchrotron
from dodal.devices.vmxm.vmxm_attenuator import VmxmAttenuator
from dodal.devices.zebra import (
    Zebra,
)

import hyperion.log
from hyperion.device_setup_plans.manipulate_sample import move_x_y_z
from hyperion.device_setup_plans.setup_zebra import (
    set_zebra_shutter_to_manual,
)
from hyperion.exceptions import WarningException
from hyperion.external_interaction.callbacks.xray_centre.callback_collection import (
    XrayCentreCallbackCollection,
)
from hyperion.parameters import external_parameters
from hyperion.parameters.constants import SIM_BEAMLINE
from hyperion.tracing import TRACER
from hyperion.utils.context import device_composite_from_context, setup_context

if TYPE_CHECKING:
    from hyperion.parameters.plan_specific.gridscan_internal_params import (
        GridscanInternalParameters,
    )


@dataclasses.dataclass
class VmxmFlyScanXRayCentreComposite:
    """All devices which are directly or indirectly required by this plan"""

    attenuator: VmxmAttenuator
    backlight: Backlight
    eiger: EigerDetector
    fast_grid_scan: FastGridScan
    # smargon: Smargon
    synchrotron: Synchrotron
    zebra: Zebra

    # @property
    # def sample_motors(self) -> Smargon:
    #     """Convenience alias with a more user-friendly name"""
    #     return self.smargon


def create_devices(context: BlueskyContext) -> VmxmFlyScanXRayCentreComposite:
    """Creates the devices required for the plan and connect to them"""
    return device_composite_from_context(context, VmxmFlyScanXRayCentreComposite)


def wait_for_gridscan_valid(fgs_motors: FastGridScan, timeout=0.5):
    hyperion.log.LOGGER.info("Waiting for valid fgs_params")
    SLEEP_PER_CHECK = 0.1
    times_to_check = int(timeout / SLEEP_PER_CHECK)
    for _ in range(times_to_check):
        scan_invalid = yield from bps.rd(fgs_motors.scan_invalid)
        pos_counter = yield from bps.rd(fgs_motors.position_counter)
        hyperion.log.LOGGER.debug(
            f"Scan invalid: {scan_invalid} and position counter: {pos_counter}"
        )
        if not scan_invalid and pos_counter == 0:
            hyperion.log.LOGGER.info("Gridscan scan valid and position counter reset")
            return
        yield from bps.sleep(SLEEP_PER_CHECK)
    raise WarningException("Scan invalid - pin too long/short/bent and out of range")


def tidy_up_plans(fgs_composite: VmxmFlyScanXRayCentreComposite):
    hyperion.log.LOGGER.info("Tidying up Zebra")
    yield from set_zebra_shutter_to_manual(fgs_composite.zebra)


@bpp.set_run_key_decorator("run_gridscan")
@bpp.run_decorator(md={"subplan_name": "run_gridscan"})
def run_gridscan(
    fgs_composite: VmxmFlyScanXRayCentreComposite,
    parameters: GridscanInternalParameters,
    md={
        "plan_name": "run_gridscan",
    },
):
    # sample_motors = fgs_composite.sample_motors

    # # Currently gridscan only works for omega 0, see #
    # with TRACER.start_span("moving_omega_to_0"):
    #     yield from bps.abs_set(sample_motors.omega, 0)

    fgs_motors = fgs_composite.fast_grid_scan

    # TODO: Check topup gate
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
        hyperion.log.LOGGER.info("Kicking off")
        yield from bps.kickoff(fgs_motors)

        yield from bps.complete(fgs_motors, wait=True)

    hyperion.log.LOGGER.info("Waiting for arming to finish")
    yield from bps.wait("ready_for_data_collection")
    yield from bps.stage(fgs_composite.eiger)

    with TRACER.start_span("do_fgs"):
        yield from do_fgs()

    yield from bps.abs_set(fgs_motors.z_steps, 0, wait=False)


def setup_vmxm_zebra_for_gridscan(
    zebra: Zebra, group="setup_zebra_for_gridscan", wait=False
):
    # VMXm-specific
    yield from bps.abs_set(zebra.output.out_pvs[4], 1, group=group)

    if wait:
        yield from bps.wait(group)


@bpp.set_run_key_decorator("run_gridscan_and_move")
@bpp.run_decorator(md={"subplan_name": "run_gridscan_and_move"})
def run_gridscan_and_move(
    fgs_composite: VmxmFlyScanXRayCentreComposite,
    parameters: GridscanInternalParameters,
    subscriptions: XrayCentreCallbackCollection,
):
    """A multi-run plan which runs a gridscan, gets the results from zocalo
    and moves to the centre of mass determined by zocalo"""

    # We get the initial motor positions so we can return to them on zocalo failure
    # initial_xyz = np.array(
    #     [
    #         (yield from bps.rd(fgs_composite.sample_motors.x)),
    #         (yield from bps.rd(fgs_composite.sample_motors.y)),
    #         (yield from bps.rd(fgs_composite.sample_motors.z)),
    #     ]
    # )

    yield from setup_vmxm_zebra_for_gridscan(fgs_composite.zebra)

    hyperion.log.LOGGER.info("Starting grid scan")

    yield from run_gridscan(fgs_composite, parameters)

    # the data were submitted to zocalo by the zocalo callback during the gridscan,
    # but results may not be ready, and need to be collected regardless.
    # it might not be ideal to block for this, see #327
    # xray_centre, _ = subscriptions.zocalo_handler.wait_for_results(initial_xyz)

    # # once we have the results, go to the appropriate position
    # hyperion.log.LOGGER.info("Moving to centre of mass.")
    # with TRACER.start_span("move_to_result"):
    #     yield from move_x_y_z(fgs_composite.sample_motors, *xray_centre, wait=True)


def transmission_for_collection_wrapper(
    plan,
    attenuator: VmxmAttenuator,
    desired_transmission_fraction: float,
):
    """Sets the transmission for the data collection, esuring the xbpm feedback is valid
    this wrapper should be run around every data collection.

    XBPM feedback isn't reliable during collections due to:
     * Objects (e.g. attenuator) crossing the beam can cause large (incorrect) feedback movements
     * Lower transmissions/higher energies are less reliable for the xbpm

    So we need to keep the transmission at 100% and the feedback on when not collecting
    and then turn it off and set the correct transmission for collection. The feedback
    mostly accounts for slow thermal drift so it is safe to assume that the beam is
    stable during a collection.

    Args:
        plan: The plan performing the data collection
        xbpm_feedback (XBPMFeedback): The XBPM device that is responsible for keeping
                                      the beam in position
        attenuator (Attenuator): The attenuator used to set transmission
        desired_transmission_fraction (float): The desired transmission for the collection
    """

    def _inner_plan():
        yield from bps.mv(attenuator, desired_transmission_fraction)
        return (yield from plan)

    def _set_transmission_to_1():
        yield from bps.mv(attenuator, 1.0)

    return (
        yield from finalize_wrapper(
            _inner_plan(),
            _set_transmission_to_1(),
        )
    )


transmission_for_collection_decorator = make_decorator(
    transmission_for_collection_wrapper
)


def vmxm_flyscan_xray_centre(
    composite: VmxmFlyScanXRayCentreComposite,
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



    #@bpp.subs_decorator(  # subscribe the RE to nexus, ispyb, and zocalo callbacks
    #    list(subscriptions)  # must be the outermost decorator to receive the metadata
    #)
    @bpp.set_run_key_decorator("run_gridscan_move_and_tidy")
    @bpp.run_decorator(  # attach experiment metadata to the start document
        md={
            "subplan_name": "run_gridscan_move_and_tidy",
            "hyperion_internal_parameters": parameters.json(),
        }
    )
    @bpp.finalize_decorator(lambda: tidy_up_plans(composite))
    @transmission_for_collection_decorator(
        composite.attenuator,
        parameters.hyperion_params.ispyb_params.transmission_fraction,
    )
    def run_gridscan_and_move_and_tidy(fgs_composite, params, comms):
        yield from bps.mv(
            composite.attenuator,
            parameters.hyperion_params.ispyb_params.transmission_fraction,
        )

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
