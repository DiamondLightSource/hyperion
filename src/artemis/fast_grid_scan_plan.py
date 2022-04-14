import os
import sys
from collections import namedtuple

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

import argparse
from dataclasses import dataclass

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
from bluesky import RunEngine
from bluesky.log import config_bluesky_logging
from bluesky.utils import ProgressBarManager
from dataclasses_json import dataclass_json
from ophyd.log import config_ophyd_logging
from src.artemis.devices.eiger import DetectorParams, EigerDetector
from src.artemis.devices.fast_grid_scan import (
    FastGridScan,
    GridScanParams,
    set_fast_grid_scan_params,
)
from src.artemis.devices.zebra import Zebra
from src.artemis.ispyb.ispyb_dataclass import IspybParams, Point2D, Point3D

config_bluesky_logging(file="/tmp/bluesky.log", level="DEBUG")
config_ophyd_logging(file="/tmp/ophyd.log", level="DEBUG")

# Clear odin errors and check initialised
# If in error clean up
# Setup beamline
# Store in ISPyB
# Start nxgen
# Start analysis run collection
SIM_BEAMLINE = "BL03S"


@dataclass_json
@dataclass
class FullParameters:
    beamline: str = SIM_BEAMLINE
    grid_scan_params: GridScanParams = GridScanParams(
        x_steps=5,
        y_steps=10,
        x_step_size=0.1,
        y_step_size=0.1,
        dwell_time=0.2,
        x_start=0.0,
        y1_start=0.0,
        z1_start=0.0,
    )
    detector_params: DetectorParams = DetectorParams(
        current_energy=100,
        exposure_time=0.1,
        acquisition_id="test",
        directory="/tmp",
        prefix="file_name",
        detector_distance=100.0,
        omega_start=0.0,
        omega_increment=0.1,
        num_images=10,
        use_roi_mode=False,
    )
    ispyb_params: IspybParams = IspybParams(
        sample_id=None,
        visit_path="",
        undulator_gap=None,
        pixels_per_micron_x=None,
        pixels_per_micron_y=None,
        upper_left=Point2D(x=None, y=None),
        sample_barcode=None,
        position=Point3D(x=None, y=None, z=None),
        synchrotron_mode=None,
        xtal_snapshots=None,
        run_number=None,
        transmission=None,
        flux=None,
        wavelength=None,
        beam_size_x=None,
        beam_size_y=None,
        slit_gap_size_x=None,
        slit_gap_size_y=None,
        focal_spot_size_x=None,
        focal_spot_size_y=None,
        comment="",
        resolution=None,
    )


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
