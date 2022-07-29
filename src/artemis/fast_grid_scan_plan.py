import argparse
import os

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
from bluesky import RunEngine
from bluesky.log import config_bluesky_logging
from bluesky.utils import ProgressBarManager
from ophyd.log import config_ophyd_logging

from src.artemis.devices.eiger import EigerDetector
from src.artemis.devices.fast_grid_scan import set_fast_grid_scan_params
from src.artemis.devices.fast_grid_scan_composite import FGSComposite
from src.artemis.devices.slit_gaps import SlitGaps
from src.artemis.devices.synchrotron import Synchrotron
from src.artemis.devices.undulator import Undulator
from src.artemis.ispyb.store_in_ispyb import StoreInIspyb2D, StoreInIspyb3D
from src.artemis.nexus_writing.write_nexus import NexusWriter
from src.artemis.parameters import SIM_BEAMLINE, FullParameters
from src.artemis.zocalo_interaction import run_end, run_start, wait_for_result

config_bluesky_logging(file="/tmp/bluesky.log", level="DEBUG")
config_ophyd_logging(file="/tmp/ophyd.log", level="DEBUG")

# Tolerance for how close omega must start to 0
OMEGA_TOLERANCE = 0.1


def update_params_from_epics_devices(
    parameters: FullParameters,
    undulator: Undulator,
    synchrotron: Synchrotron,
    slit_gap: SlitGaps,
):
    parameters.ispyb_params.undulator_gap = yield from bps.rd(undulator.gap)
    parameters.ispyb_params.synchrotron_mode = yield from bps.rd(
        synchrotron.machine_status.synchrotron_mode
    )
    parameters.ispyb_params.slit_gap_size_x = yield from bps.rd(slit_gap.xgap)
    parameters.ispyb_params.slit_gap_size_y = yield from bps.rd(slit_gap.ygap)


@bpp.run_decorator()
def run_gridscan(
    fgs_composite: FGSComposite,
    eiger: EigerDetector,
    parameters: FullParameters,
):
    sample_motors = fgs_composite.sample_motors

    current_omega = yield from bps.rd(sample_motors.omega, default_value=0)
    assert abs(current_omega - parameters.detector_params.omega_start) < OMEGA_TOLERANCE
    assert (
        abs(current_omega) < OMEGA_TOLERANCE
    )  # This should eventually be removed, see #154

    yield from update_params_from_epics_devices(
        parameters,
        fgs_composite.undulator,
        fgs_composite.synchrotron,
        fgs_composite.slit_gaps,
    )

    ispyb_config = os.environ.get("ISPYB_CONFIG_PATH", "TEST_CONFIG")
    ispyb = (
        StoreInIspyb3D(ispyb_config)
        if parameters.grid_scan_params.is_3d_grid_scan
        else StoreInIspyb2D(ispyb_config)
    )

    datacollection_ids, _, datacollection_group_id = ispyb.store_grid_scan(parameters)

    for id in datacollection_ids:
        run_start(id)

    fgs_motors = fgs_composite.fast_grid_scan
    zebra = fgs_composite.zebra

    # TODO: Check topup gate
    yield from set_fast_grid_scan_params(fgs_motors, parameters.grid_scan_params)

    @bpp.stage_decorator([zebra, eiger, fgs_motors])
    def do_fgs():
        yield from bps.kickoff(fgs_motors)
        yield from bps.complete(fgs_motors, wait=True)

    with NexusWriter(parameters):
        yield from do_fgs()

    current_time = ispyb.get_current_time_string()
    for id in datacollection_ids:
        ispyb.update_grid_scan_with_end_time_and_status(
            current_time,
            "DataCollection Successful",
            id,
            datacollection_group_id,
        )

    for id in datacollection_ids:
        run_end(id)

    xray_centre = wait_for_result(datacollection_group_id)
    xray_centre_motor_position = (
        parameters.grid_scan_params.grid_position_to_motor_position(xray_centre)
    )

    yield from bps.mv(sample_motors.omega, parameters.detector_params.omega_start)

    # After moving omega we need to wait for x, y and z to have finished moving too
    yield from bps.wait(sample_motors)

    yield from bps.mv(
        sample_motors.x,
        xray_centre_motor_position.x,
        sample_motors.y,
        xray_centre_motor_position.y,
        sample_motors.z,
        xray_centre_motor_position.z,
    )


def get_plan(parameters: FullParameters):
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

    return run_gridscan(fast_grid_scan_composite, eiger, parameters)


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

    RE(get_plan(parameters))
