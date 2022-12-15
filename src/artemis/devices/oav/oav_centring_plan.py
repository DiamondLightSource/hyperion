import bluesky.plan_stubs as bps
import numpy as np
from bluesky.run_engine import RunEngine

from artemis.devices.backlight import Backlight
from artemis.devices.I03Smargon import I03Smargon
from artemis.devices.oav.oav_calculations import (
    camera_coordinates_to_xyz,
    check_x_within_bounds,
    extract_coordinates_from_rotation_data,
    find_midpoint,
    get_rotation_increment,
    keep_inside_bounds,
)
from artemis.devices.oav.oav_detector import OAV, ColorMode, EdgeOutputArrayImageType
from artemis.devices.oav.oav_errors import (
    OAVError_WaveformAllZero,
    OAVError_ZoomLevelNotFound,
)
from artemis.devices.oav.oav_parameters import OAVParameters
from artemis.log import LOGGER
from artemis.parameters import SIM_BEAMLINE

# Z and Y bounds are hardcoded into GDA (we don't want to exceed them). We should look
# at streamlining this
_Z_LOWER_BOUND = _Y_LOWER_BOUND = -1500
_Z_UPPER_BOUND = _Y_UPPER_BOUND = 1500

# The smargon can  rotate indefinitely, so the [high/low]_limit_travel is set as 0 to
# reflect this. Despite this, Neil would like to have omega to oscillate so we will
# hard code limits so gridscans will switch rotation directions and |omega| will stay pretty low.
_DESIRED_HIGH_LIMIT = 181


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

    yield from bps.abs_set(oav.snapshot.input_pv, parameters.input_plugin + ".CAM")

    zoom_level_str = f"{float(parameters.zoom)}x"
    if zoom_level_str not in oav.zoom_controller.allowed_zooms:
        raise OAVError_ZoomLevelNotFound(
            f"Found {zoom_level_str} as a zoom level but expected one of {oav.zoom_controller.allowed_zooms}"
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


def rotate_pin_and_collect_positional_data(
    oav: OAV, smargon: I03Smargon, rotations: int, omega_high_limit
):
    """
    Calculate relevant spacial values (waveforms, and pixel positions) at each rotation and save them in lists.

    Args:
        points: the number of rotation points
    Yields:
        Movement message from each of the rotations
        Relevant lists for each rotation:
            x_positions: the x positions of centres
            y_positions: the y positions of centres
            widths: the widths between the top and bottom waveforms at the centre point
            omega_angles: the angle of the goniometer at which the measurement was taken
            tip_x_positions: the measured x tip at a given rotation
            tip_y_positions: the measured y tip at a given rotation
    """
    smargon.wait_for_connection()
    current_omega = yield from bps.rd(smargon.omega)

    # The angle to rotate by on each iteration.
    increment = get_rotation_increment(rotations, current_omega, omega_high_limit)

    # Arrays to hold positions data of the pin at each rotation,
    # these need to be np arrays for their use in centring.
    x_positions = np.array([], dtype=np.int32)
    y_positions = np.array([], dtype=np.int32)
    widths = np.array([], dtype=np.int32)
    omega_angles = np.array([], dtype=np.int32)
    tip_x_positions = np.array([], dtype=np.int32)
    tip_y_positions = np.array([], dtype=np.int32)

    for i in range(rotations):
        current_omega = yield from bps.rd(smargon.omega)
        top = np.array((yield from bps.rd(oav.mxsc.top)))

        bottom = np.array((yield from bps.rd(oav.mxsc.bottom)))
        tip_x = yield from bps.rd(oav.mxsc.tip_x)
        tip_y = yield from bps.rd(oav.mxsc.tip_y)

        for waveform in (top, bottom):
            if np.all(waveform == 0):
                raise OAVError_WaveformAllZero(
                    f"Error at rotation {current_omega}, one of the waveforms is all 0"
                )

        (x, y, width) = find_midpoint(top, bottom)
        # Build arrays of edges and width, and store corresponding gonomega
        x_positions = np.append(x_positions, x)
        y_positions = np.append(y_positions, y)
        widths = np.append(widths, width)
        omega_angles = np.append(omega_angles, current_omega)
        tip_x_positions = np.append(tip_x_positions, tip_x)
        tip_y_positions = np.append(tip_y_positions, tip_y)

        # rotate the pin to take next measurement, unless it's the last measurement
        if i < rotations - 1:
            yield from bps.mv(
                smargon.omega,
                current_omega + increment,
            )

    return (
        x_positions,
        y_positions,
        widths,
        omega_angles,
        tip_x_positions,
        tip_y_positions,
    )


def get_waveforms_to_image_scale(oav: OAV):
    """
    Returns the scale of the image. The standard calculation for the image is based
    on a size of (1024, 768) so we require these scaling factors.
    Args:
        x_size: the x size of the image, in pixels
        y_size: the y size of the image, in pixels
    Returns:
        The (x,y) where x, y is the dimensions of the image in microns
    """
    image_size_x = yield from bps.rd(oav.cam.array_size.array_size_x)
    image_size_y = yield from bps.rd(oav.cam.array_size.array_size_x)
    waveform_size_x = yield from bps.rd(oav.mxsc.waveform_size_x)
    waveform_size_y = yield from bps.rd(oav.mxsc.waveform_size_y)
    return image_size_x / waveform_size_x, image_size_y / waveform_size_y


def centring_plan(
    oav: OAV,
    parameters: OAVParameters,
    smargon: I03Smargon,
    backlight: Backlight,
    max_run_num=3,
    rotation_points=6,
):
    """
    Will attempt to find the OAV centre using rotation points.
    I03 gets the number of rotation points from gda.mx.loop.centring.omega.steps which defaults to 6.
    If it is unsuccessful in finding the points it will try centering a default maximum of 3 times.
    """

    LOGGER.info("Starting loop centring")
    yield from bps.wait()

    # Set relevant PVs to whatever the config dictates.
    yield from pre_centring_setup_oav(oav, backlight, parameters)

    # If omega  can rotate indefinitely (indicated by high_limit_travel=0), we set the hard coded limit.
    omega_high_limit = yield from bps.rd(smargon.omega.high_limit_travel)
    if not omega_high_limit:
        omega_high_limit = _DESIRED_HIGH_LIMIT

    # The image resolution may not correspond to the (1024, 768) of the waveform, then we have to scale
    # waveform pixels to get the camera pixels.
    x_scale, y_scale = yield from get_waveforms_to_image_scale(oav)

    motor_xyz = np.array(
        [
            (yield from bps.rd(smargon.x)),
            (yield from bps.rd(smargon.y)),
            (yield from bps.rd(smargon.z)),
        ],
        dtype=np.float64,
    )

    # We attempt to find the centre `max_run_num` times...
    run_num = 0
    while run_num < max_run_num:

        # Spin the goniometer and capture data from the camera at each rotation_point.
        (
            x_positions,
            y_positions,
            widths,
            omega_angles,
            tip_x_positions,
            tip_y_positions,
        ) = yield from rotate_pin_and_collect_positional_data(
            oav, smargon, rotation_points, omega_high_limit
        )

        # Filters the data captured at rotation and formats it in terms of x,y,z and angles.
        (
            x_pixels,
            y_pixels,
            z_pixels,
            best_omega_angle,
            best_omega_angle_orthogonal,
        ) = extract_coordinates_from_rotation_data(
            x_positions, y_positions, widths, omega_angles
        )

        # Adjust waveform values to match the camera pixels.
        x_pixels *= x_scale
        y_pixels *= y_scale
        z_pixels *= y_scale

        # Adjust x_pixels if it is too far away from the pin.
        tip_x = np.median(tip_x_positions)
        x_pixels = check_x_within_bounds(
            parameters.max_tip_distance_pixels, tip_x, x_pixels
        )

        # Get the beam distance from the centre (in pixels).
        (
            beam_distance_x_pixels,
            beam_distance_y_pixels,
        ) = parameters.calculate_beam_distance(x_pixels, y_pixels)

        # Add the beam distance to the current motor position (adjusting for the changes in coordinate system
        # and the from the angle).
        motor_xyz += camera_coordinates_to_xyz(
            beam_distance_x_pixels,
            beam_distance_y_pixels,
            best_omega_angle,
            parameters.micronsPerXPixel,
            parameters.micronsPerYPixel,
        )

        if run_num == max_run_num - 1:
            # If it's the last run we adjust the z value.
            beam_distance_z_pixels = parameters.calculate_beam_distance(
                x_pixels, z_pixels
            )[1]

            motor_xyz += camera_coordinates_to_xyz(
                0,
                beam_distance_z_pixels,
                best_omega_angle_orthogonal,
                parameters.micronsPerXPixel,
                parameters.micronsPerYPixel,
            )

        # If the x value exceeds the stub offsets, reset it to the stub offsets
        motor_xyz[1] = keep_inside_bounds(motor_xyz[1], _Y_LOWER_BOUND, _Y_UPPER_BOUND)
        motor_xyz[2] = keep_inside_bounds(motor_xyz[2], _Z_LOWER_BOUND, _Z_UPPER_BOUND)

        run_num += 1
        print("motor_xyz", run_num, motor_xyz)

        yield from bps.mv(
            smargon.x, motor_xyz[0], smargon.y, motor_xyz[1], smargon.z, motor_xyz[2]
        )

    # We've moved to the best x,y,z already. Now rotate to the widest pin angle.
    yield from bps.mv(smargon.omega, best_omega_angle)
    LOGGER.info("Finished loop centring")


if __name__ == "__main__":
    beamline = SIM_BEAMLINE
    oav = OAV(name="oav", prefix=beamline)

    smargon: I03Smargon = I03Smargon(name="smargon", prefix=beamline)
    backlight: Backlight = Backlight(name="backlight", prefix=beamline)
    parameters = OAVParameters(
        "src/artemis/devices/unit_tests/test_OAVCentring.json",
        "src/artemis/devices/unit_tests/test_jCameraManZoomLevels.xml",
        "src/artemis/devices/unit_tests/test_display.configuration",
    )
    oav.wait_for_connection()
    smargon.wait_for_connection()
    RE = RunEngine()
    RE(centring_plan(oav, parameters, smargon, backlight))
