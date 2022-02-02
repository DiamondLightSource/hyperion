import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from src.artemis.devices.eiger import DetectorParams, EigerDetector
from src.artemis.devices.fast_grid_scan import (
    FastGridScan,
    GridScanParams,
    set_fast_grid_scan_params,
)
import bluesky.preprocessors as bpp
import bluesky.plan_stubs as bps
from bluesky import RunEngine
from bluesky.callbacks import LiveTable
from bluesky.utils import ProgressBarManager

from src.artemis.devices.zebra import Zebra
from src.artemis.devices.det_dim_constants import EIGER2_X_16M_SIZE
import argparse
from epics import caput
from src.artemis.devices.det_dist_to_beam_converter import (
    DetectorDistanceToBeamXYConverter,
)

from ophyd.log import config_ophyd_logging
from bluesky.log import config_bluesky_logging

from bluesky.plans import scan
from ophyd.sim import motor1

config_bluesky_logging(file="/tmp/bluesky.log", level="DEBUG")
config_ophyd_logging(file="/tmp/ophyd.log", level="DEBUG")

# Clear odin errors and check initialised
# If in error clean up
# Setup beamline
# Store in ISPyB
# Start nxgen
# Start analysis run collection

DETECTOR = EIGER2_X_16M_SIZE
USE_ROI = False
GRID_SCAN_PARAMS = GridScanParams(
    x_steps=5,
    y_steps=10,
    x_step_size=0.1,
    y_step_size=0.1,
    dwell_time=0.2,
    x_start=0.0,
    y1_start=0.0,
    z1_start=0.0,
)
DETECTOR_PARAMS = DetectorParams(
    current_energy=100,
    exposure_time=0.1,
    acquisition_id="test",
    directory="/tmp",
    prefix="file_name",
    detector_distance=100.0,
    omega_start=0.0,
    omega_increment=0.1,
    num_images=10,
)
DET_TO_DIST_CONVERTER = DetectorDistanceToBeamXYConverter(
    os.path.join(
        os.path.dirname(__file__), "devices", "det_dist_to_beam_XY_converter.txt"
    )
)


@bpp.run_decorator()
def run_gridscan(fgs: FastGridScan, zebra: Zebra, eiger: EigerDetector):
    # TODO: Check topup gate
    yield from set_fast_grid_scan_params(fgs, GRID_SCAN_PARAMS)

    eiger.detector_size_constants = DETECTOR
    eiger.use_roi_mode = USE_ROI
    eiger.detector_params = DETECTOR_PARAMS
    eiger.beam_xy_converter = DET_TO_DIST_CONVERTER

    @bpp.stage_decorator([zebra, eiger, fgs])
    def do_fgs():
        yield from bps.kickoff(fgs)
        yield from bps.complete(fgs, wait=True)

    yield from do_fgs()


def do_scan(beamline_prefix: str):
    fast_grid_scan = FastGridScan(
        name="fgs", prefix=f"{beamline_prefix}-MO-SGON-01:FGS:"
    )
    eiger = EigerDetector(name="eiger", prefix=f"{beamline_prefix}-EA-EIGER-01:")
    zebra = Zebra(name="zebra", prefix=f"{beamline_prefix}-EA-ZEBRA-01:")

    RE = RunEngine({})
    RE.waiting_hook = ProgressBarManager()

    RE(run_gridscan(fast_grid_scan, zebra, eiger))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--beamline", help="The beamline prefix this is being run on", default="BL03S"
    )
    args = parser.parse_args()
    do_scan(args.beamline)
