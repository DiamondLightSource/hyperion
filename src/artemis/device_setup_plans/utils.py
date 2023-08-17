from typing import Generator

from bluesky import plan_stubs as bps
from bluesky import preprocessors as bpp
from bluesky.utils import Msg
from dodal.devices.attenuator import Attenuator
from dodal.devices.eiger import EigerDetector


def start_preparing_data_collection_then_do_plan(
    eiger: EigerDetector,
    attenuator: Attenuator,
    transmission_fraction: float,
    plan_to_run: Generator[Msg, None, None],
    group="ready_for_data_collection",
) -> Generator[Msg, None, None]:
    """Starts preparing for the next data collection by arming the eiger and setting the
    transmission. Then runs the given plan. If the plan fails it will stop disarm the eiger.
    """
    yield from bps.abs_set(eiger.do_arm, 1, group=group)
    yield from bps.abs_set(
        attenuator,
        transmission_fraction,
        group=group,
    )

    yield from bpp.contingency_wrapper(
        plan_to_run,
        except_plan=lambda e: (yield from bps.stop(eiger)),
    )
