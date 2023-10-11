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


def _delay_to_avoid_topup(total_exposure_time, time_to_topup):
    if total_exposure_time > time_to_topup:
        LOGGER.info(
            """
            Total exposure time + time needed for x ray centering exceeds time to
            next top up. Collection delayed until top up done.
            """
        )
        return True
    LOGGER.info(
        """
        Total exposure time less than time to next topup. Proceeding with collection.
        """
    )
    return False


def check_topup_and_wait_if_necessary(
    synchrotron: Synchrotron,
    params: DetectorParams,
    ops_time: float = 30.0,  # Account for xray centering, rotation speed, etc
):
    """A small plan to check if topup gating is permitted and sleep until the topup\
        is over if it starts before the end of collection.

    Args:
        synchrotron (Synchrotron): Synchrotron device.
        params (DetectorParams): The detector parameters, used to determine length\
            of scan.
        ops_time (float, optional): Additional time to account for various operations,\
            eg. x-ray centering. In seconds. Defaults to 30.0.
    """
    if _in_decay_mode(
        synchrotron.top_up.start_countdown.get()
    ) or not _gating_permitted(synchrotron.machine_status.synchrotron_mode.get()):
        time_to_wait = 0
        # yield from bps.null()
    else:
        tot_exposure_time = (
            params.exposure_time * params.full_number_of_images + ops_time
        )
        time_to_topup = synchrotron.top_up.start_countdown.get()
        time_to_wait = (
            synchrotron.top_up.end_countdown.get()
            if _delay_to_avoid_topup(tot_exposure_time, time_to_topup)
            else 0.0
        )

    yield from bps.sleep(time_to_wait)
