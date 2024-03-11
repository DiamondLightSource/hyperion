from __future__ import annotations

import dataclasses
import math
from typing import TYPE_CHECKING, Tuple

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import numpy as np
from blueapi.core import BlueskyContext
from dodal.devices.backlight import Backlight
from dodal.devices.oav.oav_detector import OAV
from dodal.devices.oav.pin_image_recognition import PinTipDetection
from dodal.devices.oav.pin_image_recognition.utils import NONE_VALUE
from dodal.devices.smargon import Smargon

from hyperion.device_setup_plans.setup_oav import (
    pre_centring_setup_oav,
    wait_for_tip_to_be_found,
)
from hyperion.log import LOGGER
from hyperion.parameters.constants import CONST
from hyperion.utils.context import device_composite_from_context

if TYPE_CHECKING:
    from dodal.devices.oav.oav_parameters import OAVParameters


@dataclasses.dataclass
class OavGridDetectionComposite:
    """All devices which are directly or indirectly required by this plan"""

    backlight: Backlight
    oav: OAV
    smargon: Smargon
    pin_tip_detection: PinTipDetection


def create_devices(context: BlueskyContext) -> OavGridDetectionComposite:
    return device_composite_from_context(context, OavGridDetectionComposite)


def get_min_and_max_y_of_pin(
    top: np.ndarray, bottom: np.ndarray, full_image_height_px: int
) -> Tuple[int, int]:
    """Gives the minimum and maximum y that would cover the whole pin.

    First filters out where no edge was found or the edge covers the full image.
    If this results in no edges found then returns a min/max that covers the full image
    """
    filtered_top = top[np.where((top != 0) & (top != NONE_VALUE))]
    min_y = min(filtered_top) if len(filtered_top) else 0
    filtered_bottom = bottom[
        np.where((bottom != full_image_height_px) & (bottom != NONE_VALUE))
    ]
    max_y = max(filtered_bottom) if len(filtered_bottom) else full_image_height_px
    return min_y, max_y


@bpp.run_decorator()
def grid_detection_plan(
    composite: OavGridDetectionComposite,
    parameters: OAVParameters,
    snapshot_template: str,
    snapshot_dir: str,
    grid_width_microns: float,
    box_size_um: float = 20,
):
    """
    Creates the parameters for two grids that are 90 degrees from each other and
    encompass the whole of the sample as it appears in the OAV.

    Args:
        composite (OavGridDetectionComposite): Composite containing devices for doing a grid detection.
        parameters (OAVParameters): Object containing parameters for setting up the OAV
        snapshot_template (str): A template for the name of the snapshots, expected to be filled in with an angle
        snapshot_dir (str): The location to save snapshots
        grid_width_microns (int): The width of the grid to scan in microns
        box_size_um (float): The size of each box of the grid in microns
    """
    oav: OAV = composite.oav
    smargon: Smargon = composite.smargon
    pin_tip_detection: PinTipDetection = composite.pin_tip_detection

    LOGGER.info("OAV Centring: Starting grid detection centring")

    yield from bps.wait()

    # Set relevant PVs to whatever the config dictates.
    yield from pre_centring_setup_oav(oav, parameters, pin_tip_detection)

    LOGGER.info("OAV Centring: Camera set up")

    assert isinstance(oav.parameters.micronsPerXPixel, float)
    box_size_x_pixels = box_size_um / oav.parameters.micronsPerXPixel
    assert isinstance(oav.parameters.micronsPerYPixel, float)
    box_size_y_pixels = box_size_um / oav.parameters.micronsPerYPixel

    grid_width_pixels = int(grid_width_microns / oav.parameters.micronsPerXPixel)

    # The FGS uses -90 so we need to match it
    for angle in [0, -90]:
        yield from bps.mv(smargon.omega, angle)
        # need to wait for the OAV image to update
        # See #673 for improvements
        yield from bps.sleep(CONST.HARDWARE.OAV_REFRESH_DELAY)

        tip_x_px, tip_y_px = yield from wait_for_tip_to_be_found(pin_tip_detection)

        LOGGER.info(f"Tip is at x,y: {tip_x_px},{tip_y_px}")

        top_edge = np.array((yield from bps.rd(pin_tip_detection.triggered_top_edge)))
        bottom_edge = np.array(
            (yield from bps.rd(pin_tip_detection.triggered_bottom_edge))
        )

        full_image_height_px = yield from bps.rd(oav.cam.array_size.array_size_y)

        # only use the area from the start of the pin onwards
        top_edge = top_edge[tip_x_px : tip_x_px + grid_width_pixels]
        bottom_edge = bottom_edge[tip_x_px : tip_x_px + grid_width_pixels]
        LOGGER.info(f"OAV Edge detection top: {list(top_edge)}")
        LOGGER.info(f"OAV Edge detection bottom: {list(bottom_edge)}")

        min_y, max_y = get_min_and_max_y_of_pin(
            top_edge, bottom_edge, full_image_height_px
        )

        grid_height_px = max_y - min_y

        y_steps: int = math.ceil(grid_height_px / box_size_y_pixels)

        # Panda not configured to run a half complete snake so enforce even rows on first grid
        # See https://github.com/DiamondLightSource/hyperion/wiki/PandA-constant%E2%80%90motion-scanning#motion-program-summary
        if y_steps % 2 and angle == 0:
            LOGGER.debug(
                f"Forcing number of rows in first grid to be even: Adding an extra row onto bottom of first grid and shifting grid upwards by {box_size_y_pixels/2}"
            )
            y_steps += 1
            min_y -= box_size_y_pixels / 2
            max_y += box_size_y_pixels / 2
            grid_height_px += box_size_y_pixels

        LOGGER.info(f"Drawing snapshot {grid_width_pixels} by {grid_height_px}")

        x_steps = (math.ceil(grid_width_pixels / box_size_x_pixels),)

        upper_left = (tip_x_px, min_y)

        yield from bps.abs_set(oav.snapshot.top_left_x, upper_left[0])
        yield from bps.abs_set(oav.snapshot.top_left_y, upper_left[1])
        yield from bps.abs_set(oav.snapshot.box_width, box_size_x_pixels)
        yield from bps.abs_set(oav.snapshot.num_boxes_x, x_steps)
        yield from bps.abs_set(oav.snapshot.num_boxes_y, y_steps)

        snapshot_filename = snapshot_template.format(angle=abs(angle))

        yield from bps.abs_set(oav.snapshot.filename, snapshot_filename)
        yield from bps.abs_set(oav.snapshot.directory, snapshot_dir)
        yield from bps.trigger(oav.snapshot, wait=True)

        yield from bps.create("snapshot_to_ispyb")

        yield from bps.read(oav.snapshot)
        yield from bps.read(smargon)
        yield from bps.save()

        LOGGER.info(
            f"Grid calculated at {angle}: {x_steps}px by {y_steps}px starting at {upper_left}px"
        )
