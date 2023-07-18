from __future__ import annotations

import argparse
from typing import TYPE_CHECKING, Callable

import bluesky.plan_stubs as bps
from bluesky import RunEngine
from bluesky.plans import grid_scan
from bluesky.utils import ProgressBarManager
from dodal.beamlines import i03
from dodal.beamlines.i03 import Smargon
from dodal.devices.aperturescatterguard import AperturePositions
from dodal.devices.eiger import DetectorParams

from artemis.log import LOGGER
from artemis.parameters import external_parameters
from artemis.parameters.beamline_parameters import (
    GDABeamlineParameters,
    get_beamline_prefixes,
)
from artemis.parameters.constants import BEAMLINE_PARAMETER_PATHS, SIM_BEAMLINE
from artemis.tracing import TRACER

if TYPE_CHECKING:
    import numpy as np

    from artemis.external_interaction.callbacks.stepped_grid_scan.stepped_grid_scan_callback_collection import (
        SteppedGridScanCallbackCollection,
    )
    from artemis.parameters.plan_specific.stepped_grid_scan_internal_params import (
        SteppedGridScanInternalParameters,
    )


class SteppedGridScanComposite:
    """A device consisting of all the Devices required for a stepped grid scan."""

    sample_motors: Smargon

    def __init__(
        self,
        aperture_positions: AperturePositions = None,
        detector_params: DetectorParams = None,
        fake: bool = False,
    ):
        self.sample_motors = i03.smargon(fake_with_ophyd_sim=fake)


stepped_grid_scan_composite: SteppedGridScanComposite | None = None


def get_beamline_parameters():
    return GDABeamlineParameters.from_file(BEAMLINE_PARAMETER_PATHS["i03"])


def create_devices():
    """Creates the devices required for the plan and connect to them"""
    global stepped_grid_scan_composite
    prefixes = get_beamline_prefixes()
    LOGGER.info(
        f"Creating devices for {prefixes.beamline_prefix} and {prefixes.insertion_prefix}"
    )
    aperture_positions = AperturePositions.from_gda_beamline_params(
        get_beamline_parameters()
    )
    LOGGER.info("Connecting to EPICS devices...")
    stepped_grid_scan_composite = SteppedGridScanComposite(
        aperture_positions=aperture_positions
    )
    LOGGER.info("Connected.")


def move_xyz(
    sample_motors,
    xray_centre_motor_position: np.array,
    md={
        "plan_name": "move_xyz",
    },
):
    """Move 'sample motors' to a specific motor position (e.g. a position obtained
    from gridscan processing results)"""
    LOGGER.info(f"Moving Smargon x, y, z to: {xray_centre_motor_position}")
    yield from bps.mv(
        sample_motors.x,
        xray_centre_motor_position.x,
        sample_motors.y,
        xray_centre_motor_position.y,
        sample_motors.z,
        xray_centre_motor_position.z,
    )


def tidy_up_plans(composite: SteppedGridScanComposite):
    LOGGER.info("Tidying up Zebra")


def run_gridscan(
    composite: SteppedGridScanComposite,
    parameters: SteppedGridScanInternalParameters,
    md={
        "plan_name": "run_gridscan",
    },
):
    sample_motors = composite.sample_motors

    # Currently gridscan only works for omega 0, see #
    with TRACER.start_span("moving_omega_to_0"):
        yield from bps.abs_set(sample_motors.omega, 0)

    def do_stepped_grid_scan():
        LOGGER.info("About to yeald from grid_scan")
        detectors = []
        grid_args = [sample_motors.x, 0, 40, 5, sample_motors.y, 0, 40, 5]
        yield from grid_scan(
            detectors, *grid_args, snake_axes=True, per_step=do_at_each_step, md={}
        )

    with TRACER.start_span("do_stepped_grid_scan"):
        yield from do_stepped_grid_scan()


def run_gridscan_and_move(
    composite: SteppedGridScanComposite,
    parameters: SteppedGridScanInternalParameters,
    subscriptions: SteppedGridScanCallbackCollection,
):
    """A multi-run plan which runs a gridscan, gets the results from zocalo
    and moves to the centre of mass determined by zocalo"""

    # While the gridscan is happening we want to write out nexus files and trigger zocalo
    def gridscan_with_subscriptions(composite, params):
        LOGGER.info("Starting stepped grid scan")
        yield from run_gridscan(composite, params)

    yield from gridscan_with_subscriptions(composite, parameters)


def get_plan(
    parameters: SteppedGridScanInternalParameters,
    subscriptions: SteppedGridScanCallbackCollection,
) -> Callable:
    """Create the plan to run the grid scan based on provided parameters.

    The ispyb handler should be added to the whole gridscan as we want to capture errors
    at any point in it.

    Args:
        parameters (SteppedGridScanInternalParameters): The parameters to run the scan.

    Returns:
        Generator: The plan for the gridscan
    """

    assert stepped_grid_scan_composite is not None

    def run_gridscan_and_move_and_tidy(composite, params, comms):
        yield from run_gridscan_and_move(composite, params, comms)

    return run_gridscan_and_move_and_tidy(
        stepped_grid_scan_composite, parameters, subscriptions
    )


def take_reading(dets, name="primary"):
    LOGGER.info("take_reading")
    yield from bps.trigger_and_read(dets, name)


def move_per_step(step, pos_cache):
    LOGGER.info("move_per_step")
    yield from bps.move_per_step(step, pos_cache)


def do_at_each_step(detectors, step, pos_cache):
    motors = step.keys()
    yield from move_per_step(step, pos_cache)
    yield from take_reading(list(detectors) + list(motors))


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
    from artemis.parameters.internal_parameters.plan_specific.stepped_grid_scan_internal_params import (
        SteppedGridScanInternalParameters,
    )

    parameters = SteppedGridScanInternalParameters(external_parameters.from_file())
    subscriptions = SteppedGridScanCallbackCollection.from_params(parameters)

    create_devices()

    RE(get_plan(parameters, subscriptions))
