import bluesky.plan_stubs as bps
from dodal.devices.detector import DetectorParams
from dodal.devices.synchrotron import Synchrotron, SynchrotronMode

from hyperion.log import LOGGER

ALLOWED_MODES = [SynchrotronMode.USER, SynchrotronMode.SPECIAL]
DECAY_MODE_CTDW = -1


def _in_decay_mode(time_to_topup):
    if time_to_topup == DECAY_MODE_CTDW:
        LOGGER.info("Machine in decay mode, gating disabled")
        return True
    return False


def _gating_permitted(machine_mode):
    if machine_mode not in ALLOWED_MODES:
        LOGGER.info("Machine not in allowed mode, gating top up enabled.")
        return True
    return False


def _delay_to_avoid_topup(total_run_time, time_to_topup):
    if total_run_time > time_to_topup:
        LOGGER.info(
            """
            Total rum time for this collection exceeds time to next top up.
            Collection delayed until top up done.
            """
        )
        return True
    LOGGER.info(
        """
        Total run time less than time to next topup. Proceeding with collection.
        """
    )
    return False


def wait_for_topup_complete(synchrotron):
    start = yield from bps.rd(synchrotron.top_up.start_countdown)
    while start == 0:
        yield from bps.sleep(0.1)
        start = yield from bps.rd(synchrotron.top_up.start_countdown)


def check_topup_and_wait_if_necessary(
    synchrotron: Synchrotron,
    params: DetectorParams,
    ops_time: float,  # Account for xray centering, rotation speed, etc
):  # See https://github.com/DiamondLightSource/hyperion/issues/932
    """A small plan to check if topup gating is permitted and sleep until the topup\
        is over if it starts before the end of collection.

    Args:
        synchrotron (Synchrotron): Synchrotron device.
        params (DetectorParams): The detector parameters, used to determine length\
            of scan.
        ops_time (float): Additional time to account for various operations,\
            eg. x-ray centering. In seconds. Defaults to 30.0.
    """
    machine_mode = yield from bps.rd(synchrotron.machine_status.synchrotron_mode)
    time_to_topup = yield from bps.rd(synchrotron.top_up.start_countdown)
    if _in_decay_mode(time_to_topup) or not _gating_permitted(machine_mode):
        yield from bps.null()
        return
    tot_run_time = params.exposure_time * params.full_number_of_images + ops_time
    end_topup = yield from bps.rd(synchrotron.top_up.end_countdown)
    time_to_wait = (
        end_topup if _delay_to_avoid_topup(tot_run_time, time_to_topup) else 0.0
    )

    yield from bps.sleep(time_to_wait)

    check_start = yield from bps.rd(synchrotron.top_up.start_countdown)
    if check_start == 0:
        yield from wait_for_topup_complete(synchrotron)
