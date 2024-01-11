import dataclasses
from typing import Generator

import bluesky.plan_stubs as bps
import numpy as np
from blueapi.core import BlueskyContext
from bluesky.utils import Msg
from dodal.devices.areadetector.plugins.MXSC import PinTipDetect
from dodal.devices.backlight import Backlight
from dodal.devices.oav.oav_detector import OAV
from dodal.devices.oav.oav_parameters import OAV_CONFIG_JSON, OAVParameters
from dodal.devices.oav.pin_image_recognition import PinTipDetection
from dodal.devices.smargon import Smargon

from hyperion.device_setup_plans.setup_oav import (
    Pixel,
    get_move_required_so_that_beam_is_at_pixel,
    pre_centring_setup_oav,
    wait_for_tip_to_be_found_ad_mxsc,
    wait_for_tip_to_be_found_ophyd,
)
from hyperion.exceptions import WarningException
from hyperion.log import LOGGER
from hyperion.parameters.constants import (
    OAV_REFRESH_DELAY,
    PIN_TIP_SOURCE,
    PinTipSource,
)
from hyperion.utils.context import device_composite_from_context

DEFAULT_STEP_SIZE = 0.5


@dataclasses.dataclass
class PinTipCentringComposite:
    """All devices which are directly or indirectly required by this plan"""

    backlight: Backlight
    oav: OAV
    smargon: Smargon
    pin_tip_detection: PinTipDetection


def create_devices(context: BlueskyContext) -> PinTipCentringComposite:
    return device_composite_from_context(context, PinTipCentringComposite)


def trigger_and_return_pin_tip(
    pin_tip: PinTipDetect | PinTipDetection,
) -> Generator[Msg, None, Pixel]:
    if PIN_TIP_SOURCE == PinTipSource.AD_MXSC_PLUGIN:
        yield from bps.trigger(pin_tip, wait=True)
    tip_x_y_px = yield from bps.rd(pin_tip)
    LOGGER.info(f"Pin tip found at {tip_x_y_px}")
    return tip_x_y_px


def move_pin_into_view(
    oav: OAV,
    smargon: Smargon,
    ophyd_pin_tip_detection: PinTipDetection,
    step_size_mm: float = DEFAULT_STEP_SIZE,
    max_steps: int = 2,
) -> Generator[Msg, None, Pixel]:
    """Attempt to move the pin into view and return the tip location in pixels if found.
    The gonio x is moved in a number of discrete steps to find the pin. If the move
    would take it past its limit, it moves to the limit instead.

    Args:
        oav (OAV): The OAV to detect the tip with
        smargon (Smargon): The gonio to move the tip
        step_size (float, optional): Distance to move the gonio (in mm) for each
                                    step of the search. Defaults to 0.5.
        max_steps (int, optional): The number of steps to search with. Defaults to 2.

    Raises:
        WarningException: Error if the pin tip is never found

    Returns:
        Tuple[int, int]: The location of the pin tip in pixels
    """

    def pin_tip_valid(pin_x: float):
        return (
            pin_x != 0
            and pin_x != oav.mxsc.pin_tip.INVALID_POSITION[0]
            and pin_x is not None
        )

    for _ in range(max_steps):
        tip_x_px, tip_y_px = yield from trigger_and_return_pin_tip(
            oav.mxsc.pin_tip
            if PIN_TIP_SOURCE == PinTipSource.AD_MXSC_PLUGIN
            else ophyd_pin_tip_detection
        )

        if pin_tip_valid(tip_x_px):
            return (tip_x_px, tip_y_px)

        if tip_x_px == 0:
            # Pin is off in the -ve direction
            step_size_mm = -step_size_mm

        smargon_x = yield from bps.rd(smargon.x.user_readback)
        ideal_move_to_find_pin = float(smargon_x) + step_size_mm
        move_within_limits = max(
            min(ideal_move_to_find_pin, smargon.x.high_limit), smargon.x.low_limit
        )
        if move_within_limits != ideal_move_to_find_pin:
            LOGGER.warning(
                f"Pin tip is off screen, and moving {step_size_mm} mm would cross limits, "
                f"moving to {move_within_limits} instead"
            )
        yield from bps.mv(smargon.x, move_within_limits)

        # Some time for the view to settle after the move
        yield from bps.sleep(OAV_REFRESH_DELAY)

    tip_x_px, tip_y_px = yield from trigger_and_return_pin_tip(oav.mxsc.pin_tip)

    if not pin_tip_valid(tip_x_px):
        raise WarningException(
            "Pin tip centring failed - pin too long/short/bent and out of range"
        )
    else:
        return (tip_x_px, tip_y_px)


def move_smargon_warn_on_out_of_range(
    smargon: Smargon, position: np.ndarray | list[float] | tuple[float, float, float]
):
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
    composite: PinTipCentringComposite,
    tip_offset_microns: float,
    oav_config_file: str = OAV_CONFIG_JSON,
):
    """Finds the tip of the pin and moves to roughly the centre based on this tip. Does
    this at both the current omega angle and +90 deg from this angle so as to get a
    centre in 3D.

    Args:
        tip_offset_microns (float): The x offset from the tip where the centre is assumed
                                    to be.
    """
    oav: OAV = composite.oav
    smargon: Smargon = composite.smargon
    oav_params = OAVParameters("pinTipCentring", oav_config_file)
    ophyd_pin_tip_detection = composite.pin_tip_detection

    tip_offset_px = int(tip_offset_microns / oav.parameters.micronsPerXPixel)

    def offset_and_move(tip: Pixel):
        pixel_to_move_to = (tip[0] + tip_offset_px, tip[1])
        position_mm = yield from get_move_required_so_that_beam_is_at_pixel(
            smargon, pixel_to_move_to, oav.parameters
        )
        LOGGER.info(f"Tip centring moving to : {position_mm}")
        yield from move_smargon_warn_on_out_of_range(smargon, position_mm)

    LOGGER.info(f"Tip offset in pixels: {tip_offset_px}")

    # need to wait for the OAV image to update
    # See #673 for improvements
    yield from bps.sleep(0.3)

    yield from pre_centring_setup_oav(oav, oav_params, ophyd_pin_tip_detection)

    tip = yield from move_pin_into_view(oav, smargon, ophyd_pin_tip_detection)
    yield from offset_and_move(tip)

    yield from bps.mvr(smargon.omega, 90)

    # need to wait for the OAV image to update
    # See #673 for improvements
    yield from bps.sleep(0.3)

    if PIN_TIP_SOURCE == PinTipSource.AD_MXSC_PLUGIN:
        LOGGER.info("Acquiring pin-tip from AD MXSC plugin")
        tip = yield from wait_for_tip_to_be_found_ad_mxsc(oav.mxsc)
    elif PIN_TIP_SOURCE == PinTipSource.OHPYD_DEVICE:
        LOGGER.info("Acquiring pin-tip from ophyd device")
        tip = yield from wait_for_tip_to_be_found_ophyd(ophyd_pin_tip_detection)
    yield from offset_and_move(tip)
