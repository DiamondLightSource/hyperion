from __future__ import annotations

import argparse
import dataclasses
from typing import TYPE_CHECKING, Any

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
from blueapi.core import BlueskyContext, MsgGenerator
from bluesky.run_engine import RunEngine
from bluesky.utils import ProgressBarManager
from dodal.devices.backlight import VmxmBacklight
from dodal.devices.eiger import EigerDetector
from dodal.devices.fast_grid_scan_2d import FastGridScan2D
from dodal.devices.fast_grid_scan_2d import (
    set_fast_grid_scan_params as set_flyscan_params,
)
from dodal.devices.synchrotron import Synchrotron
from dodal.devices.vmxm.vmxm_attenuator import VmxmAttenuator
from dodal.devices.zebra import (
    Zebra,
)

import hyperion.log
from hyperion.device_setup_plans.setup_zebra import (
    set_zebra_shutter_to_manual,
)
from hyperion.exceptions import WarningException
from hyperion.external_interaction.callbacks.xray_centre.callback_collection import (
    VmxmFastGridScanCallbackCollection,
)
from hyperion.parameters import external_parameters
from hyperion.parameters.constants import ISPYB_PLAN_NAME, SIM_BEAMLINE
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
    backlight: VmxmBacklight
    eiger: EigerDetector
    fast_grid_scan: FastGridScan2D
    synchrotron: Synchrotron
    zebra: Zebra


def create_devices(context: BlueskyContext) -> VmxmFlyScanXRayCentreComposite:
    """Creates the devices required for the plan and connect to them"""
    return device_composite_from_context(context, VmxmFlyScanXRayCentreComposite)


def wait_for_gridscan_valid(fgs_motors: FastGridScan2D, timeout=0.5):
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
    raise WarningException("Scan invalid")


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
    fgs_motors = fgs_composite.fast_grid_scan

    yield from bps.create(name=ISPYB_PLAN_NAME)
    yield from bps.read(fgs_composite.synchrotron.machine_status.synchrotron_mode)
    yield from bps.save()

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
    # note: VMXm-specific
    vmxm_zebra_input = 4
    vmxm_zebra_output = 1
    yield from bps.abs_set(
        zebra.output.out_pvs[vmxm_zebra_input], vmxm_zebra_output, group=group
    )

    if wait:
        yield from bps.wait(group)


@bpp.set_run_key_decorator("run_gridscan_and_move")
@bpp.run_decorator(md={"subplan_name": "run_gridscan_and_move"})
def run_gridscan_and_move(
    fgs_composite: VmxmFlyScanXRayCentreComposite,
    parameters: GridscanInternalParameters,
    subscriptions: VmxmFastGridScanCallbackCollection,
):
    yield from setup_vmxm_zebra_for_gridscan(fgs_composite.zebra)

    hyperion.log.LOGGER.info("Starting grid scan")

    yield from run_gridscan(fgs_composite, parameters)


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

    subscriptions = VmxmFastGridScanCallbackCollection.from_params(parameters)

    @bpp.subs_decorator(  # subscribe the RE to nexus, ispyb callbacks
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
    subscriptions = VmxmFastGridScanCallbackCollection.from_params(parameters)

    context = setup_context(wait_for_connection=True)
    composite = create_devices(context)

    RE(vmxm_flyscan_xray_centre(composite, parameters))
