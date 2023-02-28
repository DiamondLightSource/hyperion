import math

import bluesky.plan_stubs as bps
import numpy as np
from bluesky.run_engine import RunEngine

from artemis.devices.backlight import Backlight
from artemis.devices.I03Smargon import I03Smargon
from artemis.devices.oav.oav_detector import OAV, ColorMode, EdgeOutputArrayImageType
from artemis.devices.oav.oav_errors import OAVError_ZoomLevelNotFound
from artemis.devices.oav.oav_parameters import OAVParameters
from artemis.log import LOGGER, set_up_logging_handlers


# Turn on edge detect
def start_mxsc(oav: OAV, input_plugin, min_callback_time, filename):
    """
    Sets PVs relevant to edge detection plugin.

    Args:
        input_plugin: link to the camera stream
        min_callback_time: the value to set the minimum callback time to
        filename: filename of the python script to detect edge waveforms from camera stream.
    Returns: None
    """
    yield from bps.abs_set(oav.mxsc.input_plugin_pv, input_plugin)

    # Turns the area detector plugin on
    yield from bps.abs_set(oav.mxsc.enable_callbacks_pv, 1)

    # Set the minimum time between updates of the plugin
    yield from bps.abs_set(oav.mxsc.min_callback_time_pv, min_callback_time)

    # Stop the plugin from blocking the IOC and hogging all the CPU
    yield from bps.abs_set(oav.mxsc.blocking_callbacks_pv, 0)

    # Set the python file to use for calculating the edge waveforms
    current_filename = yield from bps.rd(oav.mxsc.py_filename)
    if current_filename != filename:
        LOGGER.info(f"Current python file is {current_filename}, setting to {filename}")
        yield from bps.abs_set(oav.mxsc.py_filename, filename)
        yield from bps.abs_set(oav.mxsc.read_file, 1)

    # Image annotations
    yield from bps.abs_set(oav.mxsc.draw_tip, True)
    yield from bps.abs_set(oav.mxsc.draw_edges, True)

    # Use the original image type for the edge output array
    yield from bps.abs_set(oav.mxsc.output_array, EdgeOutputArrayImageType.ORIGINAL)


def pre_centring_setup_oav(oav: OAV, parameters: OAVParameters):
    """Setup OAV PVs with required values."""

    parameters.load_parameters_from_json()

    yield from bps.abs_set(oav.cam.color_mode, ColorMode.RGB1)
    yield from bps.abs_set(oav.cam.acquire_period, parameters.acquire_period)
    yield from bps.abs_set(oav.cam.acquire_time, parameters.exposure)
    yield from bps.abs_set(oav.cam.gain, parameters.gain)

    # select which blur to apply to image
    yield from bps.abs_set(oav.mxsc.preprocess_operation, parameters.preprocess)

    # sets length scale for blurring
    yield from bps.abs_set(oav.mxsc.preprocess_ksize, parameters.preprocess_K_size)

    # Canny edge detect
    yield from bps.abs_set(
        oav.mxsc.canny_lower_threshold,
        parameters.canny_edge_lower_threshold,
    )
    yield from bps.abs_set(
        oav.mxsc.canny_upper_threshold,
        parameters.canny_edge_upper_threshold,
    )
    # "Close" morphological operation
    yield from bps.abs_set(oav.mxsc.close_ksize, parameters.close_ksize)

    # Sample detection
    yield from bps.abs_set(
        oav.mxsc.sample_detection_scan_direction, parameters.direction
    )
    yield from bps.abs_set(
        oav.mxsc.sample_detection_min_tip_height,
        parameters.minimum_height,
    )

    # Connect CAM output to MXSC input
    yield from start_mxsc(
        oav,
        parameters.input_plugin + "." + "proc",
        parameters.min_callback_time,
        parameters.filename,
    )

    yield from bps.abs_set(oav.snapshot.input_pv, parameters.input_plugin + ".MXSC")

    zoom_level_str = f"{float(parameters.zoom)}x"
    if zoom_level_str not in oav.zoom_controller.allowed_zoom_levels:
        raise OAVError_ZoomLevelNotFound(
            f"Found {zoom_level_str} as a zoom level but expected one of {oav.zoom_controller.allowed_zoom_levels}"
        )

    # yield from bps.abs_set(
    #     oav.zoom_controller.level,
    #     zoom_level_str,
    #     wait=True,
    # )
    # yield from bps.wait()


def get_waveforms_to_image_scale(oav: OAV):
    """
    Returns the scale of the image. The standard calculation for the image is based
    on a size of (1024, 768) so we require these scaling factors.
    Args:
        oav (OAV): The OAV device in use.
    Returns:
        The (i_dimensions,j_dimensions) where n_dimensions is the scale of the camera image to the
        waveform values on the n axis.
    """
    image_size_i = yield from bps.rd(oav.cam.array_size.array_size_x)
    image_size_j = yield from bps.rd(oav.cam.array_size.array_size_y)
    waveform_size_i = yield from bps.rd(oav.mxsc.waveform_size_x)
    waveform_size_j = yield from bps.rd(oav.mxsc.waveform_size_y)
    return image_size_i / waveform_size_i, image_size_j / waveform_size_j


def grid_detection_plan(
    oav: OAV,
    smargon: I03Smargon,
    parameters: OAVParameters,
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

    # The image resolution may not correspond to the (1024, 768) of the waveform, then we have to scale
    # waveform pixels to get the camera pixels.
    i_scale, j_scale = yield from get_waveforms_to_image_scale(oav)

    upper_lefts = []
    box_numbers = []

    for angle in [0, 90]:
        yield from bps.mv(smargon.omega, angle)

        top = np.array((yield from bps.rd(oav.mxsc.top)))
        bottom = np.array((yield from bps.rd(oav.mxsc.bottom)))

        tip_i = yield from bps.rd(oav.mxsc.tip_x)
        tip_j = yield from bps.rd(oav.mxsc.tip_y)

        LOGGER.info(f"tip_i {tip_i}, tip_j {tip_j}")

        left_margin = 0
        top_margin = 0

        width = 600
        box_size = 20

        top = top[tip_i : tip_i + width]
        bottom = bottom[tip_i : tip_i + width]

        LOGGER.info(f"Top: {top}")

        LOGGER.info(f"Bottom: {bottom}")

        test_snapshot_dir = "/dls_sw/i03/software/artemis/test_snaps"

        min_y = np.min(top)
        max_y = np.max(bottom)

        LOGGER.info(f"Min/max {min_y, max_y}")

        height = max_y - min_y

        LOGGER.info(f"Drawing snapshot {width} by {height}")

        boxes = (math.ceil(width / box_size), math.ceil(height / box_size))
        box_numbers.append(boxes)

        upper_left = (tip_i - left_margin, min_y - top_margin)
        upper_lefts.append(upper_left)

        yield from bps.abs_set(oav.snapshot.top_left_x_signal, upper_left[0])
        yield from bps.abs_set(oav.snapshot.top_left_y_signal, upper_left[1])
        yield from bps.abs_set(oav.snapshot.box_width_signal, box_size)
        yield from bps.abs_set(oav.snapshot.num_boxes_x_signal, boxes[0])
        yield from bps.abs_set(oav.snapshot.num_boxes_y_signal, boxes[1])

        LOGGER.info("Triggering snapshot")

        snapshot_filename = f"test_grid_{angle}"

        yield from bps.abs_set(oav.snapshot.filename, snapshot_filename)
        yield from bps.abs_set(oav.snapshot.directory, test_snapshot_dir)
        yield from bps.trigger(oav.snapshot, wait=True)


if __name__ == "__main__":
    beamline = "BL03I"
    set_up_logging_handlers("INFO")
    oav = OAV(name="oav", prefix=beamline)
    smargon = I03Smargon(name="smargon", prefix=beamline)
    backlight: Backlight = Backlight(name="backlight", prefix=beamline)
    parameters = OAVParameters(
        "src/artemis/devices/unit_tests/test_OAVCentring.json",
        "src/artemis/devices/unit_tests/test_jCameraManZoomLevels.xml",
        "src/artemis/devices/unit_tests/test_display.configuration",
    )
    oav.wait_for_connection()
    smargon.wait_for_connection()
    RE = RunEngine()
    RE(grid_detection_plan(oav, smargon, parameters))
