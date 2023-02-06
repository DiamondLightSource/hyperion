import bluesky.plan_stubs as bps
from bluesky import RunEngine
from bluesky.run_engine import RunEngine
from dodal.devices.backlight import Backlight
from dodal.devices.oav.oav_detector import OAV, ColorMode, EdgeOutputArrayImageType
from dodal.devices.oav.oav_errors import OAVError_ZoomLevelNotFound
from dodal.devices.oav.oav_parameters import OAVParameters
from dodal.devices.smargon import Smargon

from artemis.parameters import SIM_BEAMLINE


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
    yield from bps.abs_set(oav.mxsc.py_filename, filename)
    yield from bps.abs_set(oav.mxsc.read_file, 1)

    # Image annotations
    yield from bps.abs_set(oav.mxsc.draw_tip, True)
    yield from bps.abs_set(oav.mxsc.draw_edges, True)

    # Use the original image type for the edge output array
    yield from bps.abs_set(oav.mxsc.output_array, EdgeOutputArrayImageType.ORIGINAL)


def pre_centring_setup_oav(oav: OAV, backlight: Backlight, parameters: OAVParameters):
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

    # Connect MXSC output to MJPG input
    yield from start_mxsc(
        oav,
        parameters.input_plugin + "." + parameters.mxsc_input,
        parameters.min_callback_time,
        parameters.filename,
    )

    yield from bps.abs_set(oav.snapshot.input_pv, parameters.input_plugin + ".MXSC")

    zoom_level_str = f"{float(parameters.zoom)}x"
    if zoom_level_str not in oav.zoom_controller.allowed_zoom_levels:
        raise OAVError_ZoomLevelNotFound(
            f"Found {zoom_level_str} as a zoom level but expected one of {oav.zoom_controller.allowed_zoom_levels}"
        )

    yield from bps.abs_set(
        oav.zoom_controller.level,
        zoom_level_str,
        wait=True,
    )

    yield from bps.abs_set(backlight.pos, 1)
    yield from bps.wait()

    """
    TODO: We require setting the backlight brightness to that in the json, we can't do this currently without a PV.
    """


if __name__ == "__main__":
    beamline = SIM_BEAMLINE
    oav = OAV(name="oav", prefix=beamline)

    smargon: Smargon = Smargon(name="smargon", prefix=beamline)
    backlight: Backlight = Backlight(name="backlight", prefix=beamline)
    parameters = OAVParameters(
        "src/artemis/devices/unit_tests/test_OAVCentring.json",
        "src/artemis/devices/unit_tests/test_jCameraManZoomLevels.xml",
        "src/artemis/devices/unit_tests/test_display.configuration",
    )
    oav.wait_for_connection()
    smargon.wait_for_connection()
    RE = RunEngine()
    RE(pre_centring_setup_oav(oav, backlight, parameters))
