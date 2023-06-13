from __future__ import annotations

import math
from typing import TYPE_CHECKING

import bluesky.preprocessors as bpp
import bluesky.plan_stubs as bps
import numpy as np
from bluesky.preprocessors import finalize_wrapper
from dodal.beamlines import i03
from dodal.devices.areadetector.plugins.MXSC import PinTipDetect
from dodal.devices.fast_grid_scan import GridScanParams
from dodal.devices.oav.oav_calculations import camera_coordinates_to_xyz
from dodal.devices.oav.oav_detector import OAV
from dodal.devices.smargon import Smargon

from artemis.device_setup_plans.setup_oav import pre_centring_setup_oav
from artemis.exceptions import WarningException
from artemis.log import LOGGER

if TYPE_CHECKING:
    from dodal.devices.oav.oav_parameters import OAVParameters


def create_devices():
    i03.oav()
    i03.smargon()
    i03.backlight()


def grid_detection_plan(
    parameters: OAVParameters,
    out_parameters: GridScanParams,
    snapshot_template: str,
    snapshot_dir: str,
    out_upper_left: list[float] | np.ndarray,
    width=600,
    box_size_microns=20,
):
    yield from finalize_wrapper(
        grid_detection_main_plan(
            parameters,
            out_parameters,
            snapshot_template,
            snapshot_dir,
            out_upper_left,
            width,
            box_size_microns,
        ),
        reset_oav(parameters),
    )


def wait_for_tip_to_be_found(pin_tip: PinTipDetect):
    yield from bps.trigger(pin_tip, wait=True)
    found_tip = yield from bps.rd(pin_tip)
    if found_tip == pin_tip.INVALID_POSITION:
        raise WarningException(
            f"No pin found after {pin_tip.validity_timeout.get()} seconds"
        )
    return found_tip


@bpp.run_decorator()
def grid_detection_main_plan(
    parameters: OAVParameters,
    out_parameters: GridScanParams,
    snapshot_template: str,
    snapshot_dir: str,
    out_upper_left: list[float] | np.ndarray,
    grid_width_px: int,
    box_size_um: float,
):
    """
    Creates the parameters for two grids that are 90 degrees from each other and
    encompass the whole of the sample as it appears in the OAV.

    Args:
        parameters (OAVParamaters): Object containing paramters for setting up the OAV
        out_parameters (GridScanParams): The returned parameters for the gridscan
        snapshot_template (str): A template for the name of the snapshots, expected to be filled in with an angle
        snapshot_dir (str): The location to save snapshots
        out_upper_left (Dict): The returned x, y, z value of the upper left pixel of the grid
        grid_width_px (int): The width of the grid to scan in pixels
        box_size_um (float): The size of each box of the grid in microns
    """
    oav: OAV = i03.oav()
    smargon: Smargon = i03.smargon()
    LOGGER.info("OAV Centring: Starting grid detection centring")

    yield from bps.wait()

    # Set relevant PVs to whatever the config dictates.
    yield from pre_centring_setup_oav(oav, parameters)

    LOGGER.info("OAV Centring: Camera set up")

    start_positions = []
    box_numbers = []

    box_size_x_pixels = box_size_um / parameters.micronsPerXPixel
    box_size_y_pixels = box_size_um / parameters.micronsPerYPixel

    # The FGS uses -90 so we need to match it
    for angle in [0, -90]:
        yield from bps.mv(smargon.omega, angle)
        # need to wait for the OAV image to update
        # See #673 for improvements
        yield from bps.sleep(0.3)

        tip_x_px, tip_y_px = yield from wait_for_tip_to_be_found(oav.mxsc.pin_tip)

        LOGGER.info(f"Tip is at x,y: {tip_x_px},{tip_y_px}")

        top_edge = np.array((yield from bps.rd(oav.mxsc.top)))
        bottom_edge = np.array((yield from bps.rd(oav.mxsc.bottom)))

        full_image_height_px = yield from bps.rd(oav.cam.array_size.array_size_y)

        # only use the area from the start of the pin onwards
        top_edge = top_edge[tip_x_px : tip_x_px + grid_width_px]
        bottom_edge = bottom_edge[tip_x_px : tip_x_px + grid_width_px]

        # the edge detection line can jump to the edge of the image sometimes, filter
        # those points out, and if empty after filter use the whole image
        filtered_top = list(top_edge[top_edge != 0]) or [0]
        filtered_bottom = list(bottom_edge[bottom_edge != full_image_height_px]) or [
            full_image_height_px
        ]
        min_y = min(filtered_top)
        max_y = max(filtered_bottom)
        grid_height_px = max_y - min_y

        LOGGER.info(f"Drawing snapshot {grid_width_px} by {grid_height_px}")

        boxes = (
            math.ceil(grid_width_px / box_size_x_pixels),
            math.ceil(grid_height_px / box_size_y_pixels),
        )
        box_numbers.append(boxes)

        upper_left = (tip_x_px, min_y)
        if angle == 0:
            out_upper_left[0] = int(tip_x_px)
            out_upper_left[1] = int(min_y)
        else:
            out_upper_left[2] = int(min_y)

        yield from bps.abs_set(oav.snapshot.top_left_x, upper_left[0])
        yield from bps.abs_set(oav.snapshot.top_left_y, upper_left[1])
        yield from bps.abs_set(oav.snapshot.box_width, box_size_x_pixels)
        yield from bps.abs_set(oav.snapshot.num_boxes_x, boxes[0])
        yield from bps.abs_set(oav.snapshot.num_boxes_y, boxes[1])

        snapshot_filename = snapshot_template.format(angle=abs(angle))

        yield from bps.abs_set(oav.snapshot.filename, snapshot_filename)
        yield from bps.abs_set(oav.snapshot.directory, snapshot_dir)
        yield from bps.trigger(oav.snapshot, wait=True)

        yield from bps.create("snapshot_directories")
        yield from bps.read(oav.snapshot.last_saved_path)
        yield from bps.read(oav.snapshot.last_path_outer)
        yield from bps.read(oav.snapshot.last_path_full_overlay)
        yield from bps.save()

        # Get the beam distance from the centre (in pixels).
        (
            beam_distance_i_pixels,
            beam_distance_j_pixels,
        ) = parameters.calculate_beam_distance(upper_left[0], upper_left[1])

        current_motor_xyz = np.array(
            [
                (yield from bps.rd(smargon.x)),
                (yield from bps.rd(smargon.y)),
                (yield from bps.rd(smargon.z)),
            ],
            dtype=np.float64,
        )

        # Add the beam distance to the current motor position (adjusting for the changes in coordinate system
        # and the from the angle).
        start_position = current_motor_xyz + camera_coordinates_to_xyz(
            beam_distance_i_pixels,
            beam_distance_j_pixels,
            angle,
            parameters.micronsPerXPixel,
            parameters.micronsPerYPixel,
        )
        start_positions.append(start_position)

    LOGGER.info(
        f"Calculated start position {start_positions[0][0], start_positions[0][1], start_positions[1][2]}"
    )
    out_parameters.x_start = start_positions[0][0]

    out_parameters.y1_start = start_positions[0][1]
    out_parameters.y2_start = start_positions[0][1]

    out_parameters.z1_start = start_positions[1][2]
    out_parameters.z2_start = start_positions[1][2]

    LOGGER.info(
        f"Calculated number of steps {box_numbers[0][0], box_numbers[0][1], box_numbers[1][1]}"
    )
    out_parameters.x_steps = box_numbers[0][0]
    out_parameters.y_steps = box_numbers[0][1]
    out_parameters.z_steps = box_numbers[1][1]

    LOGGER.info(f"Step sizes: {box_size_um, box_size_um, box_size_um}")
    out_parameters.x_step_size = box_size_um / 1000
    out_parameters.y_step_size = box_size_um / 1000
    out_parameters.z_step_size = box_size_um / 1000


def reset_oav(parameters: OAVParameters):
    oav = i03.oav()
    yield from bps.abs_set(oav.snapshot.input_plugin, parameters.input_plugin + ".CAM")
    yield from bps.abs_set(oav.mxsc.enable_callbacks, 0)
