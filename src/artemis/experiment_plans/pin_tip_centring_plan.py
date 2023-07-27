from typing import Generator, Tuple

import bluesky.plan_stubs as bps
from bluesky.utils import Msg
from dodal.devices.oav.oav_detector import OAV
from dodal.devices.smargon import Smargon

from artemis.exceptions import WarningException
from artemis.log import LOGGER


def move_pin_into_view(
    oav: OAV, smargon: Smargon, step_size: float = 1, max_steps: int = 1
) -> Generator[Msg, None, Tuple[int, int]]:
    """Attempt to move the pin into view and return the tip location in pixels if found.
    The gonio is moved in a number of discrete steps to find the pin.

    Args:
        oav (OAV): The OAV to detect the tip with
        smargon (Smargon): The gonio to move the tip
        step_size (float, optional): Distance to move the gonio (in mm) for each
                                    step of the search. Defaults to 1.
        max_steps (int, optional): The number of steps to search with. Defaults to 1.

    Raises:
        WarningException: Error if the pin tip is never found

    Returns:
        Tuple[int, int]: The location of the pin tip in pixels
    """

    for _ in range(max_steps):
        yield from bps.trigger(oav.mxsc.pin_tip, wait=True)
        tip_x_px, tip_y_px = yield from bps.rd(oav.mxsc.pin_tip)

        if tip_x_px == 0:
            LOGGER.warning(f"Pin is too long, moving -{step_size}mm")
            yield from bps.mvr(smargon.x, -step_size)
        elif tip_x_px == oav.mxsc.pin_tip.INVALID_POSITION[0]:
            LOGGER.warning(f"Pin is too short, moving {step_size}mm")
            yield from bps.mvr(smargon.x, step_size)
        else:
            return (tip_x_px, tip_y_px)

        # Some time for the view to settle after the move
        yield from bps.sleep(0.3)

    yield from bps.trigger(oav.mxsc.pin_tip, wait=True)
    tip_x_px, tip_y_px = yield from bps.rd(oav.mxsc.pin_tip)

    if tip_x_px == 0 or tip_x_px == oav.mxsc.pin_tip.INVALID_POSITION[0]:
        raise WarningException(
            "Pin tip centring failed - pin too long/short/bent and out of range"
        )
    else:
        return (tip_x_px, tip_y_px)
