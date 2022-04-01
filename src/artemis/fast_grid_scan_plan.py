from collections import namedtuple
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from src.artemis.devices.eiger import EigerDetector
from src.artemis.devices.fast_grid_scan import (
    FastGridScan,
    set_fast_grid_scan_params,
)
from src.artemis.nexus_writing.write_nexus import NexusWriter
from src.artemis.parameters import FullParameters, SIM_BEAMLINE

import bluesky.preprocessors as bpp
import bluesky.plan_stubs as bps
from bluesky import RunEngine
from bluesky.utils import ProgressBarManager

from src.artemis.devices.zebra import Zebra
import argparse

from ophyd.log import config_ophyd_logging
from bluesky.log import config_bluesky_logging


config_bluesky_logging(file="/tmp/bluesky.log", level="DEBUG")
config_ophyd_logging(file="/tmp/ophyd.log", level="DEBUG")

# Clear odin errors and check initialised
# If in error clean up
# Setup beamline
# Store in ISPyB
# Start nxgen
# Start analysis run collection


@bpp.run_decorator()
def run_gridscan(
    fgs: FastGridScan, zebra: Zebra, eiger: EigerDetector, parameters: FullParameters
):
    # TODO: Check topup gate
    yield from set_fast_grid_scan_params(fgs, parameters.grid_scan_params)

    @bpp.stage_decorator([zebra, eiger, fgs])
    def do_fgs():
        yield from bps.kickoff(fgs)
        yield from bps.complete(fgs, wait=True)

    with NexusWriter(parameters):
        yield from do_fgs()


def get_plan(parameters: FullParameters):
    """Create the plan to run the grid scan based on provided parameters.

    Args:
        parameters (FullParameters): The parameters to run the scan.

    Returns:
        Generator: The plan for the gridscan
    """
    fast_grid_scan = FastGridScan(
        name="fgs", prefix=f"{parameters.beamline}-MO-SGON-01:FGS:"
    )
    eiger = EigerDetector(
        parameters.detector_params,
        name="eiger",
        prefix=f"{parameters.beamline}-EA-EIGER-01:",
    )
    zebra = Zebra(name="zebra", prefix=f"{parameters.beamline}-EA-ZEBRA-01:")

    return run_gridscan(fast_grid_scan, zebra, eiger, parameters)


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
