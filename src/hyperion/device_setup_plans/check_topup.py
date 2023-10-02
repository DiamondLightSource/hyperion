import bluesky.plan_stubs as bps
from dodal.devices.detector import DetectorParams
from dodal.devices.synchrotron import Synchrotron, SynchrotronMode

from hyperion.log import LOGGER

ALLOWED_MODES = [SynchrotronMode.USER, SynchrotronMode.SPECIAL]


def _in_decay_mode(time_to_topup):
    if time_to_topup == -1:
        LOGGER.info("Decay mode, gating disabled")
        return True
    return False


def _gating_permitted(machine_mode):
    if machine_mode not in ALLOWED_MODES:
        LOGGER.info("Machne mode not in alowed list, gating top up.")
        return False
    return True


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


def check_topup_and_wait_if_before_collection_done(
    synchrotron: Synchrotron,
    params: DetectorParams,
):
    if _in_decay_mode(
        synchrotron.top_up.start_countdown.get()
    ) or not _gating_permitted(synchrotron.machine_status.synchrotron_mode.get()):
        time_to_wait = 0
        # yield from bps.null()
    else:
        tot_exposure_time = params.exposure_time * params.full_number_of_images
        time_to_topup = synchrotron.top_up.start_countdown.get()
        # Need to also consider time for xray centering ?
        time_to_wait = (
            synchrotron.top_up.end_countdown.get()
            if _delay_to_avoid_topup(tot_exposure_time, time_to_topup)
            else 0
        )

    yield from bps.sleep(time_to_wait)
