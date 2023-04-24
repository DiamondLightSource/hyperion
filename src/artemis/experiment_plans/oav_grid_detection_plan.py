from __future__ import annotations

import math
from typing import TYPE_CHECKING

import bluesky.plan_stubs as bps
import numpy as np
from bluesky.preprocessors import finalize_wrapper
from dodal import i03
from dodal.devices.fast_grid_scan import GridScanParams
from dodal.devices.oav.oav_calculations import camera_coordinates_to_xyz
from dodal.devices.oav.oav_detector import OAV
from dodal.devices.smargon import Smargon

from artemis.device_setup_plans.setup_oav import pre_centring_setup_oav
from artemis.log import LOGGER

if TYPE_CHECKING:
    from dodal.devices.oav.oav_parameters import OAVParameters


def create_devices():
    i03.oav().wait_for_connection()
    i03.smargon().wait_for_connection()
    i03.backlight().wait_for_connection()


def grid_detection_plan(
    parameters: OAVParameters,
    out_parameters: GridScanParams,
    width=600,
    box_size_microns=20,
):
    yield from finalize_wrapper(
        grid_detection_main_plan(parameters, out_parameters, width, box_size_microns),
        reset_oav(parameters),
    )


def grid_detection_main_plan(
    parameters: OAVParameters,
    out_parameters: GridScanParams,
    grid_width_px: int,
    box_size_um: int,
):
    """
    Attempts to find the centre of the pin on the oav by rotating and sampling elements.
    I03 gets the number of rotation points from gda.mx.loop.centring.omega.steps which defaults to 6.

    Args:
        oav (OAV): The OAV device in use.
        parameters (OAVParamaters): Object containing values loaded in from various parameter files in use.
        max_run_num (int): Maximum number of times to run.
        rotation_points (int): Test to see if the pin is widest `rotation_points` number of times on a full 180 degree rotation.
    """
    oav: OAV = i03.oav()
    smargon: Smargon = i03.smargon()
    LOGGER.info("OAV Centring: Starting loop centring")

    yield from bps.wait()

    # Set relevant PVs to whatever the config dictates.
    yield from pre_centring_setup_oav(oav, parameters)

    LOGGER.info("OAV Centring: Camera set up")

    start_positions = []
    box_numbers = []

    box_size_x_pixels = box_size_um / parameters.micronsPerXPixel
    box_size_y_pixels = box_size_um / parameters.micronsPerYPixel

    for angle in [0, 90]:
        yield from bps.mv(smargon.omega, angle)
        # need to wait for the OAV image to update
        # TODO improve this from just waiting some random time
        yield from bps.sleep(0.5)

        top_edge = np.array((yield from bps.rd(oav.mxsc.top)))
        bottom_edge = np.array((yield from bps.rd(oav.mxsc.bottom)))

        tip_x_px = yield from bps.rd(oav.mxsc.tip_x)
        tip_y_px = yield from bps.rd(oav.mxsc.tip_y)

        LOGGER.info(f"Tip is at x,y: {tip_x_px},{tip_y_px}")

        full_oav_image_height_px = yield from bps.rd(oav.cam.array_size.array_size_y)

        # only use the area from the start of the pin onwards
        top_edge = top_edge[tip_x_px : tip_x_px + grid_width_px]
        bottom_edge = bottom_edge[tip_x_px : tip_x_px + grid_width_px]

        # the edge detection line can jump to the edge of the image sometimes, filter
        # those points out
        min_y = np.min(top_edge[top_edge != 0])
        max_y = np.max(bottom_edge[bottom_edge != full_oav_image_height_px])
        LOGGER.info(f"Min/max {min_y, max_y}")
        # if top and bottom empty after filter use the whole image (ask neil)
        grid_height_px = max_y - min_y

        LOGGER.info(f"Drawing snapshot {grid_width_px} by {grid_height_px}")

        boxes = (
            math.ceil(grid_width_px / box_size_x_pixels),
            math.ceil(grid_height_px / box_size_y_pixels),
        )
        box_numbers.append(boxes)

        upper_left = (tip_x_px, min_y)

        yield from bps.abs_set(oav.snapshot.top_left_x, upper_left[0])
        yield from bps.abs_set(oav.snapshot.top_left_y, upper_left[1])
        yield from bps.abs_set(oav.snapshot.box_width, box_size_x_pixels)
        yield from bps.abs_set(oav.snapshot.num_boxes_x, boxes[0])
        yield from bps.abs_set(oav.snapshot.num_boxes_y, boxes[1])

        LOGGER.info("Triggering snapshot")

        snapshot_filename = (
            parameters.snapshot_1_filename
            if angle == 0
            else parameters.snapshot_2_filename
        )

        test_snapshot_dir = "/dls_sw/i03/software/artemis/test_snaps"

        yield from bps.abs_set(oav.snapshot.filename, snapshot_filename)
        yield from bps.abs_set(oav.snapshot.directory, test_snapshot_dir)
        yield from bps.trigger(oav.snapshot, wait=True)

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
        f"x_start: GDA: {out_parameters.x_start}, Artemis {start_positions[0][0]}"
    )

    LOGGER.info(
        f"y1_start: GDA: {out_parameters.y1_start}, Artemis {start_positions[0][1]}"
    )

    LOGGER.info(
        f"z1_start: GDA: {out_parameters.z1_start}, Artemis {start_positions[1][1]}"
    )

    LOGGER.info(
        f"x_step_size: GDA: {out_parameters.x_step_size}, Artemis {box_size_um}"
    )
    LOGGER.info(
        f"y_step_size: GDA: {out_parameters.y_step_size}, Artemis {box_size_um}"
    )
    LOGGER.info(
        f"z_step_size: GDA: {out_parameters.z_step_size}, Artemis {box_size_um}"
    )

    LOGGER.info(f"x_steps: GDA: {out_parameters.x_steps}, Artemis {box_numbers[0][0]}")
    LOGGER.info(f"y_steps: GDA: {out_parameters.y_steps}, Artemis {box_numbers[0][1]}")
    LOGGER.info(f"z_steps: GDA: {out_parameters.z_steps}, Artemis {box_numbers[1][1]}")


def reset_oav(parameters: OAVParameters):
    oav = i03.oav()
    yield from bps.abs_set(oav.snapshot.input_plugin, parameters.input_plugin + ".CAM")
    yield from bps.abs_set(oav.mxsc.enable_callbacks, 0)
