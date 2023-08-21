from typing import Dict, Generator

import bluesky.plan_stubs as bps
import numpy as np
from bluesky.utils import Msg
from dodal.beamlines import i03
from dodal.devices.oav.oav_detector import OAV
from dodal.devices.oav.oav_parameters import OAV_CONFIG_FILE_DEFAULTS, OAVParameters
from dodal.devices.smargon import Smargon

from hyperion.device_setup_plans.setup_oav import (
    Pixel,
    get_move_required_so_that_beam_is_at_pixel,
    pre_centring_setup_oav,
    wait_for_tip_to_be_found,
)
from hyperion.exceptions import WarningException
from hyperion.log import LOGGER


def create_devices():
    i03.oav()
    i03.smargon()
    i03.backlight()


def move_pin_into_view(
    oav: OAV, smargon: Smargon, step_size: float = 1, max_steps: int = 1
) -> Generator[Msg, None, Pixel]:
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


def move_smargon_warn_on_out_of_range(smargon: Smargon, position: np.ndarray):
    """Throws a WarningException if the specified position is out of range for the
    smargon. Otherwise moves to that position."""
    if not smargon.get_xyz_limits().position_valid(position):
        raise WarningException(
            "Pin tip centring failed - pin too long/short/bent and out of range"
        )
    yield from bps.mv(
        smargon.x,
        position[0],
        smargon.y,
        position[1],
        smargon.z,
        position[2],
    )


def pin_tip_centre_plan(
    tip_offset_microns: float,
    oav_config_files: Dict[str, str] = OAV_CONFIG_FILE_DEFAULTS,
):
    """Finds the tip of the pin and moves to roughly the centre based on this tip. Does
    this at both the current omega angle and +90 deg from this angle so as to get a
    centre in 3D.

    Args:
        tip_offset_microns (float): The x offset from the tip where the centre is assumed
                                    to be.
    """
    oav: OAV = i03.oav()
    smargon: Smargon = i03.smargon()
    oav_params = OAVParameters("pinTipCentring", **oav_config_files)

    tip_offset_px = int(tip_offset_microns / oav_params.micronsPerXPixel)

    def offset_and_move(tip: Pixel):
        pixel_to_move_to = (tip[0] + tip_offset_px, tip[1])
        position_mm = yield from get_move_required_so_that_beam_is_at_pixel(
            smargon, pixel_to_move_to, oav_params
        )
        LOGGER.info(f"Tip centring moving to : {position_mm}")
        yield from move_smargon_warn_on_out_of_range(smargon, position_mm)

    LOGGER.info(f"Tip offset in pixels: {tip_offset_px}")

    # need to wait for the OAV image to update
    # See #673 for improvements
    yield from bps.sleep(0.3)

    yield from pre_centring_setup_oav(oav, oav_params)

    tip = yield from move_pin_into_view(oav, smargon)
    yield from offset_and_move(tip)

    yield from bps.mvr(smargon.omega, 90)

    # need to wait for the OAV image to update
    # See #673 for improvements
    yield from bps.sleep(0.3)

    tip = yield from wait_for_tip_to_be_found(oav.mxsc)
    yield from offset_and_move(tip)
