from bluesky import plan_stubs as bps
from bluesky.preprocessors import finalize_wrapper, make_decorator
from dodal.devices.attenuator import Attenuator
from dodal.devices.xbpm_feedback import XBPMFeedback

from hyperion.log import LOGGER


def _check_and_pause_feedback(
    xbpm_feedback: XBPMFeedback,
    attenuator: Attenuator,
    desired_transmission_fraction: float,
):
    """Checks that the xbpm is in position before collection then turns it off.

    Args:
        xbpm_feedback (XBPMFeedback): The XBPM device that is responsible for keeping
                                      the beam in position
        attenuator (Attenuator): The attenuator used to set transmission
        desired_transmission_fraction (float): The desired transmission for the collection

    """
    yield from bps.mv(attenuator, 1.0)
    LOGGER.info("Waiting for XPBM feedback before collection")
    yield from bps.trigger(xbpm_feedback, wait=True)
    LOGGER.info(
        "XPBM feedback in position, pausing and setting transmission for collection"
    )
    yield from bps.mv(xbpm_feedback.pause_feedback, xbpm_feedback.PAUSE)
    yield from bps.mv(attenuator, desired_transmission_fraction)


def _unpause_xbpm_feedback_and_set_transmission_to_1(
    xbpm_feedback: XBPMFeedback, attenuator: Attenuator
):
    """Turns the XBPM feedback back on and sets transmission to 1 so that it keeps the
    beam aligned whilst not collecting.

    Args:
        xbpm_feedback (XBPMFeedback): The XBPM device that is responsible for keeping
                                      the beam in position
        attenuator (Attenuator): The attenuator used to set transmission
    """
    yield from bps.mv(xbpm_feedback.pause_feedback, xbpm_feedback.RUN, attenuator, 1.0)


def transmission_and_xbpm_feedback_for_collection_wrapper(
    plan,
    xbpm_feedback: XBPMFeedback,
    attenuator: Attenuator,
    desired_transmission_fraction: float,
):
    """Sets the transmission for the data collection, ensuring the xbpm feedback is valid
    this wrapper should be run around every data collection.

    XBPM feedback isn't reliable during collections due to:
     * Objects (e.g. attenuator) crossing the beam can cause large (incorrect) feedback movements
     * Lower transmissions/higher energies are less reliable for the xbpm

    So we need to keep the transmission at 100% and the feedback on when not collecting
    and then turn it off and set the correct transmission for collection. The feedback
    mostly accounts for slow thermal drift so it is safe to assume that the beam is
    stable during a collection.

    Args:
        plan: The plan performing the data collection
        xbpm_feedback (XBPMFeedback): The XBPM device that is responsible for keeping
                                      the beam in position
        attenuator (Attenuator): The attenuator used to set transmission
        desired_transmission_fraction (float): The desired transmission for the collection
    """

    def _inner_plan():
        yield from _check_and_pause_feedback(
            xbpm_feedback, attenuator, desired_transmission_fraction
        )
        return (yield from plan)

    return (
        yield from finalize_wrapper(
            _inner_plan(),
            _unpause_xbpm_feedback_and_set_transmission_to_1(xbpm_feedback, attenuator),
        )
    )


transmission_and_xbpm_feedback_for_collection_decorator = make_decorator(
    transmission_and_xbpm_feedback_for_collection_wrapper
)
