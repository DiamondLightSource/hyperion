import argparse

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
from bluesky import RunEngine
from bluesky.utils import ProgressBarManager

from artemis.devices.eiger import EigerDetector
from artemis.devices.fast_grid_scan import set_fast_grid_scan_params
from artemis.devices.fast_grid_scan_composite import FGSComposite
from artemis.devices.slit_gaps import SlitGaps
from artemis.devices.synchrotron import Synchrotron
from artemis.devices.undulator import Undulator
from artemis.fgs_communicator import FGSCommunicator
from artemis.parameters import SIM_BEAMLINE, FullParameters

# Tolerance for how close omega must start to 0
OMEGA_TOLERANCE = 0.1


def read_hardware_for_ispyb(
    undulator: Undulator,
    synchrotron: Synchrotron,
    slit_gap: SlitGaps,
):
    yield from bps.create(name="ispyb_params")
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
        # The name of this plan
        "plan_name": "move_xyz",
    },
):

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
        # The name of this plan
        "plan_name": "run_gridscan",
    },
):

    sample_motors = fgs_composite.sample_motors

    current_omega = yield from bps.rd(sample_motors.omega, default_value=0)
    assert abs(current_omega - parameters.detector_params.omega_start) < OMEGA_TOLERANCE
    assert (
        abs(current_omega) < OMEGA_TOLERANCE
    )  # This should eventually be removed, see #154

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
        yield from bps.kickoff(fgs_motors)
        yield from bps.complete(fgs_motors, wait=True)

    yield from do_fgs()


def run_gridscan_and_move(
    fgs_composite: FGSComposite,
    eiger: EigerDetector,
    parameters: FullParameters,
    communicator: FGSCommunicator,
):
    yield from run_gridscan(fgs_composite, eiger, parameters)
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

    fast_grid_scan_composite.wait_for_connection()

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
    communicator = FGSCommunicator()
    RE.subscribe(communicator)

    RE(get_plan(parameters, communicator))
