from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

import bluesky.plan_stubs as bps
import bluesky.plans as bluesky_plans
from blueapi.core import BlueskyContext, MsgGenerator
from dodal.devices.smargon import Smargon
from dodal.utils import get_beamline_name

from hyperion.log import LOGGER
from hyperion.parameters.beamline_parameters import GDABeamlineParameters
from hyperion.parameters.constants import BEAMLINE_PARAMETER_PATHS, SIM_BEAMLINE
from hyperion.tracing import TRACER
from hyperion.utils.context import device_composite_from_context

if TYPE_CHECKING:
    from hyperion.parameters.plan_specific.stepped_grid_scan_internal_params import (
        SteppedGridScanInternalParameters,
    )


@dataclasses.dataclass
class SteppedGridScanComposite:
    """All devices which are directly or indirectly required by this plan"""

    smargon: Smargon


def get_beamline_parameters():
    return GDABeamlineParameters.from_file(
        BEAMLINE_PARAMETER_PATHS[get_beamline_name(SIM_BEAMLINE)]
    )


def create_devices(context: BlueskyContext) -> SteppedGridScanComposite:
    """Creates the devices required for the plan and connect to them"""
    return device_composite_from_context(context, SteppedGridScanComposite)


def run_gridscan(
    composite: SteppedGridScanComposite,
    parameters: SteppedGridScanInternalParameters,
    md={
        "plan_name": "run_gridscan",
    },
):
    sample_motors: Smargon = composite.smargon

    # Currently gridscan only works for omega 0, see #
    with TRACER.start_span("moving_omega_to_0"):
        yield from bps.abs_set(sample_motors.omega, 0)

    def do_stepped_grid_scan():
        LOGGER.info("About to yield from grid_scan")
        detectors = []
        grid_args = [sample_motors.x, 0, 40, 5, sample_motors.y, 0, 40, 5]
        yield from bluesky_plans.grid_scan(
            detectors, *grid_args, snake_axes=True, per_step=do_at_each_step, md={}
        )

    with TRACER.start_span("do_stepped_grid_scan"):
        yield from do_stepped_grid_scan()


def get_plan(
    composite: SteppedGridScanComposite, parameters: SteppedGridScanInternalParameters
) -> MsgGenerator:
    """Create the plan to run the grid scan based on provided parameters.

    Args:
        parameters (SteppedGridScanInternalParameters): The parameters to run the scan.

    Returns:
        Generator: The plan for the gridscan
    """
    return run_gridscan(composite, parameters)


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
