from typing import Generator, Tuple

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import numpy as np
from bluesky.utils import Msg
from dodal.devices.oav.oav_calculations import camera_coordinates_to_xyz
from dodal.devices.oav.oav_detector import OAV
from dodal.devices.oav.oav_parameters import OAVParameters
from dodal.devices.smargon import Smargon
from ophyd.utils.errors import LimitError

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


def move_smargon_warn_on_out_of_range(
    smargon: Smargon, position: Tuple[float, float, float]
):
    def warn_if_limit_error(exception: Exception):
        if isinstance(exception, LimitError):
            raise WarningException(
                "Pin tip centring failed - pin too long/short/bent and out of range"
            )
        yield bps.null()

    yield from bpp.contingency_wrapper(
        bps.mv(
            smargon.x,
            position[0],
            smargon.y,
            position[1],
            smargon.z,
            position[2],
        ),
        except_plan=warn_if_limit_error,
    )


def move_so_that_beam_is_at_pixel(
    smargon: Smargon, pixel: Tuple[int, int], oav_params: OAVParameters
):
    """Move so that the given pixel is in the centre of the beam."""
    beam_distance_px: Tuple[int, int] = oav_params.calculate_beam_distance(*pixel)

    current_motor_xyz = np.array(
        [
            (yield from bps.rd(smargon.x)),
            (yield from bps.rd(smargon.y)),
            (yield from bps.rd(smargon.z)),
        ],
        dtype=np.float64,
    )
    current_angle = yield from bps.rd(smargon.omega)

    position_mm = current_motor_xyz + camera_coordinates_to_xyz(
        beam_distance_px[0],
        beam_distance_px[1],
        current_angle,
        oav_params.micronsPerXPixel,
        oav_params.micronsPerYPixel,
    )

    LOGGER.info(f"Tip centring moving to : {position_mm}")
    yield from move_smargon_warn_on_out_of_range(smargon, position_mm)
