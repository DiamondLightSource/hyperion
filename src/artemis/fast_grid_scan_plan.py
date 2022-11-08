import argparse

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
from bluesky import RunEngine
from bluesky.preprocessors import subs_decorator
from bluesky.utils import ProgressBarManager
from ophyd.utils.errors import WaitTimeoutError

import artemis.log
from artemis.devices.eiger import EigerDetector
from artemis.devices.fast_grid_scan import set_fast_grid_scan_params
from artemis.devices.fast_grid_scan_composite import FGSComposite
from artemis.devices.slit_gaps import SlitGaps
from artemis.devices.synchrotron import Synchrotron
from artemis.devices.undulator import Undulator
from artemis.fgs_communicator import FGSCommunicator
from artemis.parameters import ISPYB_PLAN_NAME, SIM_BEAMLINE, FullParameters
from artemis.tracing import TRACER


def read_hardware_for_ispyb(
    undulator: Undulator,
    synchrotron: Synchrotron,
    slit_gap: SlitGaps,
):
    artemis.log.LOGGER.debug(
        "Reading status of beamline parameters for ispyb deposition."
    )
    yield from bps.create(
        name=ISPYB_PLAN_NAME
    )  # gives name to event *descriptor* document
    yield from bps.read(undulator.gap)
    yield from bps.read(synchrotron.machine_status.synchrotron_mode)
    yield from bps.read(slit_gap.xgap)
    yield from bps.read(slit_gap.ygap)
    yield from bps.save()


@bpp.run_decorator()
def move_xyz(
    sample_motors,
    xray_centre_motor_position,
    md={
        "plan_name": "move_xyz",
    },
):
    """Move 'sample motors' to a specific motor position (e.g. a position obtained
    from gridscan processing results)"""
    yield from bps.mv(
        sample_motors.x,
        xray_centre_motor_position.x,
        sample_motors.y,
        xray_centre_motor_position.y,
        sample_motors.z,
        xray_centre_motor_position.z,
    )


@bpp.run_decorator()
def run_gridscan(
    fgs_composite: FGSComposite,
    eiger: EigerDetector,
    parameters: FullParameters,
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
        yield from read_hardware_for_ispyb(
            fgs_composite.undulator,
            fgs_composite.synchrotron,
            fgs_composite.slit_gaps,
        )

    fgs_motors = fgs_composite.fast_grid_scan
    zebra = fgs_composite.zebra

    # TODO: Check topup gate
    yield from set_fast_grid_scan_params(fgs_motors, parameters.grid_scan_params)

    @bpp.stage_decorator([zebra, eiger, fgs_motors])
    def do_fgs():
        yield from bps.wait()  # Wait for all moves to complete
        yield from bps.kickoff(fgs_motors)
        yield from bps.complete(fgs_motors, wait=True)

    with TRACER.start_span("do_fgs"):
        try:
            yield from do_fgs()
        except WaitTimeoutError:
            artemis.log.LOGGER.debug("Filewriter/staleparams timeout")

    with TRACER.start_span("move_to_z_0"):
        yield from bps.abs_set(fgs_motors.z_steps, 0, wait=False)


def run_gridscan_and_move(
    fgs_composite: FGSComposite,
    eiger: EigerDetector,
    parameters: FullParameters,
    communicator: FGSCommunicator,
):
    """A multi-run plan which runs a gridscan, gets the results from zocalo
    and moves to the centre of mass determined by zocalo"""
    # our communicator should listen to documents only from the actual grid scan
    # so we subscribe to it with our plan
    @subs_decorator(communicator)
    def gridscan_with_communicator(fgs_comp, det, params):
        yield from run_gridscan(fgs_comp, det, params)

    artemis.log.LOGGER.info("Starting grid scan")
    yield from gridscan_with_communicator(fgs_composite, eiger, parameters)

    # the data were submitted to zocalo by the communicator during the gridscan,
    # but results may not be ready.
    # it might not be ideal to block for this, see #327
    communicator.wait_for_results()

    # once we have the results, go to the appropriate position
    artemis.log.LOGGER.info("Moving to centre of mass.")
    with TRACER.start_span("move_to_result"):
        yield from move_xyz(
            fgs_composite.sample_motors, communicator.xray_centre_motor_position
        )


def get_plan(parameters: FullParameters, communicator: FGSCommunicator):
    """Create the plan to run the grid scan based on provided parameters.

    Args:
        parameters (FullParameters): The parameters to run the scan.

    Returns:
        Generator: The plan for the gridscan
    """
    artemis.log.LOGGER.info("Fetching composite plan")
    fast_grid_scan_composite = FGSComposite(
        insertion_prefix=parameters.insertion_prefix,
        name="fgs",
        prefix=parameters.beamline,
    )

    # Note, eiger cannot be currently waited on, see #166
    eiger = EigerDetector(
        parameters.detector_params,
        name="eiger",
        prefix=f"{parameters.beamline}-EA-EIGER-01:",
    )

    artemis.log.LOGGER.debug("Connecting to EPICS devices...")
    fast_grid_scan_composite.wait_for_connection()
    artemis.log.LOGGER.debug("Connected.")

    return run_gridscan_and_move(
        fast_grid_scan_composite, eiger, parameters, communicator
    )


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

    parameters = FullParameters(beamline=args.beamline)
    communicator = FGSCommunicator(parameters)

    RE(get_plan(parameters, communicator))
