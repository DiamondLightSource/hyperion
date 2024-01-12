from functools import partial
from typing import Generator, Tuple

import bluesky.plan_stubs as bps
import numpy as np
from bluesky.utils import Msg
from dodal.devices.areadetector.plugins.MXSC import MXSC
from dodal.devices.oav.oav_calculations import camera_coordinates_to_xyz
from dodal.devices.oav.oav_detector import OAV, OAVConfigParams
from dodal.devices.oav.oav_errors import OAVError_ZoomLevelNotFound
from dodal.devices.oav.oav_parameters import OAVParameters
from dodal.devices.oav.pin_image_recognition import PinTipDetection
from dodal.devices.oav.utils import ColorMode, EdgeOutputArrayImageType
from dodal.devices.smargon import Smargon

from hyperion.exceptions import WarningException
from hyperion.log import LOGGER

Pixel = Tuple[int, int]
oav_group = "oav_setup"
# Helper function to make sure we set the waiting groups correctly
set_using_group = partial(bps.abs_set, group=oav_group)


def start_mxsc(oav: OAV, min_callback_time, filename):
    """
    Sets PVs relevant to edge detection plugin.

    Args:
        min_callback_time: the value to set the minimum callback time to
        filename: filename of the python script to detect edge waveforms from camera stream.
    Returns: None
    """
    # Turns the area detector plugin on
    yield from set_using_group(oav.mxsc.enable_callbacks, 1)

    # Set the minimum time between updates of the plugin
    yield from set_using_group(oav.mxsc.min_callback_time, min_callback_time)

    # Stop the plugin from blocking the IOC and hogging all the CPU
    yield from set_using_group(oav.mxsc.blocking_callbacks, 0)

    # Set the python file to use for calculating the edge waveforms
    current_filename = yield from bps.rd(oav.mxsc.filename)
    if current_filename != filename:
        LOGGER.info(
            f"Current OAV MXSC plugin python file is {current_filename}, setting to {filename}"
        )
        yield from set_using_group(oav.mxsc.filename, filename)
        yield from set_using_group(oav.mxsc.read_file, 1)

    # Image annotations
    yield from set_using_group(oav.mxsc.draw_tip, True)
    yield from set_using_group(oav.mxsc.draw_edges, True)

    # Use the original image type for the edge output array
    yield from set_using_group(oav.mxsc.output_array, EdgeOutputArrayImageType.ORIGINAL)


def setup_pin_tip_detection_params(
    pin_tip_detect_device: MXSC | PinTipDetection, parameters: OAVParameters
):
    # select which blur to apply to image
    yield from set_using_group(
        pin_tip_detect_device.preprocess_operation, parameters.preprocess
    )

    # sets length scale for blurring
    yield from set_using_group(
        pin_tip_detect_device.preprocess_ksize, parameters.preprocess_K_size
    )

    # Canny edge detect - lower
    yield from set_using_group(
        pin_tip_detect_device.canny_lower_threshold,
        parameters.canny_edge_lower_threshold,
    )

    # Canny edge detect - upper
    yield from set_using_group(
        pin_tip_detect_device.canny_upper_threshold,
        parameters.canny_edge_upper_threshold,
    )

    # "Close" morphological operation
    yield from set_using_group(
        pin_tip_detect_device.close_ksize, parameters.close_ksize
    )

    # Sample detection direction
    yield from set_using_group(
        pin_tip_detect_device.scan_direction, parameters.direction
    )

    # Minimum height
    yield from set_using_group(
        pin_tip_detect_device.min_tip_height,
        parameters.minimum_height,
    )


def pre_centring_setup_oav(
    oav: OAV,
    parameters: OAVParameters,
    pin_tip_detection_device: PinTipDetection | MXSC,
):
    """
    Setup OAV PVs with required values.
    """
    yield from set_using_group(oav.cam.color_mode, ColorMode.RGB1)
    yield from set_using_group(oav.cam.acquire_period, parameters.acquire_period)
    yield from set_using_group(oav.cam.acquire_time, parameters.exposure)
    yield from set_using_group(oav.cam.gain, parameters.gain)

    yield from setup_pin_tip_detection_params(pin_tip_detection_device, parameters)

    yield from start_mxsc(
        oav,
        parameters.min_callback_time,
        parameters.detection_script_filename,
    )

    zoom_level_str = f"{float(parameters.zoom)}x"
    if zoom_level_str not in oav.zoom_controller.allowed_zoom_levels:
        raise OAVError_ZoomLevelNotFound(
            f"Found {zoom_level_str} as a zoom level but expected one of {oav.zoom_controller.allowed_zoom_levels}"
        )

    yield from bps.abs_set(
        oav.zoom_controller,
        zoom_level_str,
        wait=True,
    )

    # Connect MXSC output to MJPG input for debugging
    yield from set_using_group(oav.snapshot.input_plugin, "OAV.MXSC")

    yield from bps.wait(oav_group)

    """
    TODO: We require setting the backlight brightness to that in the json, we can't do this currently without a PV.
    """


def calculate_x_y_z_of_pixel(
    current_x_y_z, current_omega, pixel: Pixel, oav_params: OAVConfigParams
) -> np.ndarray:
    beam_distance_px: Pixel = oav_params.calculate_beam_distance(*pixel)

    return current_x_y_z + camera_coordinates_to_xyz(
        beam_distance_px[0],
        beam_distance_px[1],
        current_omega,
        oav_params.micronsPerXPixel,
        oav_params.micronsPerYPixel,
    )


def get_move_required_so_that_beam_is_at_pixel(
    smargon: Smargon, pixel: Pixel, oav_params: OAVConfigParams
) -> Generator[Msg, None, np.ndarray]:
    """Calculate the required move so that the given pixel is in the centre of the beam."""

    current_motor_xyz = np.array(
        [
            (yield from bps.rd(smargon.x)),
            (yield from bps.rd(smargon.y)),
            (yield from bps.rd(smargon.z)),
        ],
        dtype=np.float64,
    )
    current_angle = yield from bps.rd(smargon.omega)

    return calculate_x_y_z_of_pixel(current_motor_xyz, current_angle, pixel, oav_params)


def wait_for_tip_to_be_found_ad_mxsc(
    mxsc: MXSC,
) -> Generator[Msg, None, Tuple[int, int]]:
    pin_tip = mxsc.pin_tip
    yield from bps.trigger(pin_tip, wait=True)
    found_tip = yield from bps.rd(pin_tip)
    if found_tip == pin_tip.INVALID_POSITION:
        top_edge = yield from bps.rd(mxsc.top)
        bottom_edge = yield from bps.rd(mxsc.bottom)
        LOGGER.info(
            f"No tip found with top/bottom of {list(top_edge), list(bottom_edge)}"
        )
        raise WarningException(
            f"No pin found after {pin_tip.validity_timeout.get()} seconds"
        )
    return found_tip


def wait_for_tip_to_be_found_ophyd(
    ophyd_pin_tip_detection: PinTipDetection,
) -> Generator[Msg, None, Tuple[int, int]]:
    found_tip = yield from bps.rd(ophyd_pin_tip_detection)

    LOGGER.info("Pin tip not found, waiting a second and trying again")

    if found_tip == ophyd_pin_tip_detection.INVALID_POSITION:
        # Wait a second and then retry
        yield from bps.sleep(1)
        found_tip = yield from bps.rd(ophyd_pin_tip_detection)

    if found_tip == ophyd_pin_tip_detection.INVALID_POSITION:
        raise WarningException("No pin found")

    return found_tip  # type: ignore
