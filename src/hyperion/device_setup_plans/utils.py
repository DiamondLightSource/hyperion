from typing import Generator

from bluesky import plan_stubs as bps
from bluesky import preprocessors as bpp
from bluesky.utils import Msg
from dodal.devices.detector_motion import DetectorMotion, ShutterState
from dodal.devices.eiger import EigerDetector

from hyperion.device_setup_plans.position_detector import (
    set_detector_z_position,
    set_shutter,
)


def start_preparing_data_collection_then_do_plan(
    eiger: EigerDetector,
    detector_motion: DetectorMotion,
    detector_distance: float,
    plan_to_run: Generator[Msg, None, None],
    group="ready_for_data_collection",
) -> Generator[Msg, None, None]:
    """Starts preparing for the next data collection and then runs the
    given plan.

     Preparation consists of:
     * Arming the Eiger
     * Moving the detector to the specified position
     * Opening the detect shutter
     If the plan fails it will disarm the eiger.
    """
    yield from bps.abs_set(eiger.do_arm, 1, group=group)

    yield from set_detector_z_position(detector_motion, detector_distance, group)
    yield from set_shutter(detector_motion, ShutterState.OPEN, group)

    yield from bpp.contingency_wrapper(
        plan_to_run,
        except_plan=lambda e: (yield from bps.stop(eiger)),
    )
