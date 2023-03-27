import math
from typing import TYPE_CHECKING

import bluesky.plan_stubs as bps
import numpy as np
from dodal.devices.backlight import Backlight
from dodal.devices.fast_grid_scan import GridScanParams
from dodal.devices.oav.oav_calculations import camera_coordinates_to_xyz
from dodal.devices.oav.oav_detector import OAV
from dodal.devices.smargon import Smargon

from artemis.device_setup_plans.setup_oav import pre_centring_setup_oav
from artemis.log import LOGGER
from artemis.parameters.beamline_parameters import get_beamline_prefixes

if TYPE_CHECKING:
    from dodal.devices.oav.oav_parameters import OAVParameters

oav: OAV = None
smargon: Smargon = None
backlight: Backlight = None


def create_devices():
    global oav, smargon, backlight
    prefixes = get_beamline_prefixes()
    oav = OAV(name="oav", prefix=prefixes.beamline_prefix)
    smargon = Smargon(name="smargon", prefix=prefixes.beamline_prefix)
    backlight = Backlight(name="backlight", prefix="BL03I-EA-BL-01:")
    oav.wait_for_connection()
    smargon.wait_for_connection()
    backlight.wait_for_connection()


def grid_detection_plan(
    parameters: OAVParameters,
    subscriptions,
    out_parameters: GridScanParams,
    width=600,
    box_size_microns=20,
):
    try:
        yield from grid_detection_main_plan(
            parameters, subscriptions, out_parameters, width, box_size_microns
        )
    finally:
        yield from reset_oav(parameters)


def grid_detection_main_plan(
    parameters: OAVParameters,
    subscriptions,
    out_parameters: GridScanParams,
    width: int,
    box_size_microns: int,
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

    LOGGER.info("OAV Centring: Starting loop centring")

    yield from bps.wait()

    # Set relevant PVs to whatever the config dictates.
    yield from pre_centring_setup_oav(oav, parameters)

    LOGGER.info("OAV Centring: Camera set up")

    start_positions = []
    box_numbers = []

    box_size_x_pixels = box_size_microns / parameters.micronsPerXPixel
    box_size_y_pixels = box_size_microns / parameters.micronsPerYPixel

    for angle in [0, 90]:
        yield from bps.mv(smargon.omega, angle)
        yield from bps.sleep(0.5)

        top = np.array((yield from bps.rd(oav.mxsc.top)))
        bottom = np.array((yield from bps.rd(oav.mxsc.bottom)))

        tip_i = yield from bps.rd(oav.mxsc.tip_x)
        tip_j = yield from bps.rd(oav.mxsc.tip_y)

        LOGGER.info(f"tip_i {tip_i}, tip_j {tip_j}")

        left_margin = 0
        top_margin = 0

        top = top[tip_i : tip_i + width]
        bottom = bottom[tip_i : tip_i + width]

        LOGGER.info(f"Top: {top}")

        LOGGER.info(f"Bottom: {bottom}")

        min_y = np.min(top[top != 0])

        full_oav_image_height = yield from bps.rd(oav.cam.array_size.array_size_y)

        max_y = np.max(bottom[bottom != full_oav_image_height])

        # if top and bottom empty after filter use the whole image (ask neil)

        LOGGER.info(f"Min/max {min_y, max_y}")

        height = max_y - min_y

        LOGGER.info(f"Drawing snapshot {width} by {height}")

        boxes = (
            math.ceil(width / box_size_x_pixels),
            math.ceil(height / box_size_y_pixels),
        )
        box_numbers.append(boxes)

        upper_left = (tip_i - left_margin, min_y - top_margin)

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
        f"x_step_size: GDA: {out_parameters.x_step_size}, Artemis {box_size_microns}"
    )
    LOGGER.info(
        f"y_step_size: GDA: {out_parameters.y_step_size}, Artemis {box_size_microns}"
    )
    LOGGER.info(
        f"z_step_size: GDA: {out_parameters.z_step_size}, Artemis {box_size_microns}"
    )

    LOGGER.info(f"x_steps: GDA: {out_parameters.x_steps}, Artemis {box_numbers[0][0]}")
    LOGGER.info(f"y_steps: GDA: {out_parameters.y_steps}, Artemis {box_numbers[0][1]}")
    LOGGER.info(f"z_steps: GDA: {out_parameters.z_steps}, Artemis {box_numbers[1][1]}")


def reset_oav(parameters: OAVParameters):
    yield from bps.abs_set(oav.snapshot.input_plugin, parameters.input_plugin + ".CAM")
    yield from bps.abs_set(oav.mxsc.enable_callbacks, 0)
