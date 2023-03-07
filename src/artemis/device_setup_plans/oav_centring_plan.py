import bluesky.plan_stubs as bps
import numpy as np
from bluesky.run_engine import RunEngine
from dodal.devices.backlight import Backlight
from dodal.devices.oav.oav_calculations import (
    camera_coordinates_to_xyz,
    check_i_within_bounds,
    extract_pixel_centre_values_from_rotation_data,
    find_midpoint,
    get_rotation_increment,
    keep_inside_bounds,
)
from dodal.devices.oav.oav_detector import OAV, ColorMode, EdgeOutputArrayImageType
from dodal.devices.oav.oav_errors import (
    OAVError_WaveformAllZero,
    OAVError_ZoomLevelNotFound,
)
from dodal.devices.oav.oav_parameters import OAVParameters
from dodal.devices.smargon import Smargon

from artemis.log import LOGGER, set_up_logging_handlers

# Z and Y bounds are hardcoded into GDA (we don't want to exceed them). We should look
# at streamlining this
_Y_LOWER_BOUND = _Z_LOWER_BOUND = -1500
_Y_UPPER_BOUND = _Z_UPPER_BOUND = 1500

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

    # Connect MXSC output to MJPG input
    yield from start_mxsc(
        oav,
        parameters.input_plugin + "." + parameters.mxsc_input,
        parameters.min_callback_time,
        parameters.filename,
    )

    yield from bps.abs_set(oav.snapshot.input_pv, parameters.input_plugin + ".CAM")

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
    yield from bps.wait()

    """
    TODO: We require setting the backlight brightness to that in the json, we can't do this currently without a PV.
    """


def rotate_pin_and_collect_positional_data(
    oav: OAV, smargon: Smargon, rotations: int, omega_high_limit: float
):
    """
    Calculate relevant spacial values (waveforms, and pixel positions) at each rotation and save them in lists.

    Args:
        oav (OAV): The oav device to rotate and sample MXSC data from.
        smargon (Smargon): The smargon controller device.
        rotations (int): The number of rotations to sample.
        omega_high_limit (float): The motor limit that shouldn't be exceeded.
    Returns:
        Relevant lists for each rotation, where index n corresponds to data at rotation n:
            i_positions: the i positions of centres (x in camera coordinates)
            j_positions: the j positions of centres (y in camera coordinates)
            widths: the widths between the top and bottom waveforms at the centre point
            omega_angles: the angle of the goniometer at which the measurement was taken
            tip_i_positions: the measured i tip at a given rotation
            tip_j_positions: the measured j tip at a given rotation
    """
    smargon.wait_for_connection()
    current_omega = yield from bps.rd(smargon.omega)

    # The angle to rotate by on each iteration.
    increment = get_rotation_increment(rotations, current_omega, omega_high_limit)

    # Arrays to hold positions data of the pin at each rotation,
    # these need to be np arrays for their use in centring.
    i_positions = np.array([], dtype=np.int32)
    j_positions = np.array([], dtype=np.int32)
    widths = np.array([], dtype=np.int32)
    omega_angles = np.array([], dtype=np.int32)
    tip_i_positions = np.array([], dtype=np.int32)
    tip_j_positions = np.array([], dtype=np.int32)

    for n in range(rotations):
        current_omega = yield from bps.rd(smargon.omega)
        top = np.array((yield from bps.rd(oav.mxsc.top)))

        bottom = np.array((yield from bps.rd(oav.mxsc.bottom)))
        tip_i = yield from bps.rd(oav.mxsc.tip_x)
        tip_j = yield from bps.rd(oav.mxsc.tip_y)

        for waveform in (top, bottom):
            if np.all(waveform == 0):
                raise OAVError_WaveformAllZero(
                    f"Error at rotation {current_omega}, one of the waveforms is all 0"
                )

        (i, j, width) = find_midpoint(top, bottom)
        i_positions = np.append(i_positions, i)
        j_positions = np.append(j_positions, j)
        widths = np.append(widths, width)
        omega_angles = np.append(omega_angles, current_omega)
        tip_i_positions = np.append(tip_i_positions, tip_i)
        tip_j_positions = np.append(tip_j_positions, tip_j)

        # rotate the pin to take next measurement, unless it's the last measurement
        if n < rotations - 1:
            yield from bps.mv(
                smargon.omega,
                current_omega + increment,
            )

    return (
        i_positions,
        j_positions,
        widths,
        omega_angles,
        tip_i_positions,
        tip_j_positions,
    )


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


def centring_plan(
    oav: OAV,
    parameters: OAVParameters,
    smargon: Smargon,
    max_run_num=3,
    rotation_points=6,
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

    # If omega  can rotate indefinitely (indicated by high_limit_travel=0), we set the hard coded limit.
    omega_high_limit = yield from bps.rd(smargon.omega.high_limit_travel)
    if not omega_high_limit:
        omega_high_limit = _DESIRED_HIGH_LIMIT

    # The image resolution may not correspond to the (1024, 768) of the waveform, then we have to scale
    # waveform pixels to get the camera pixels.
    i_scale, j_scale = yield from get_waveforms_to_image_scale(oav)

    # array for holding the current xyz position of the motor.
    motor_xyz = np.array(
        [
            (yield from bps.rd(smargon.x)),
            (yield from bps.rd(smargon.y)),
            (yield from bps.rd(smargon.z)),
        ],
        dtype=np.float64,
    )

    LOGGER.info(f"OAV Centring: Starting xyz, {motor_xyz}")

    # We attempt to find the centre `max_run_num` times...
    for run_num in range(max_run_num):
        # Spin the goniometer and capture data from the camera at each rotation_point.
        (
            i_positions,
            j_positions,
            widths,
            omega_angles,
            tip_i_positions,
            tip_j_positions,
        ) = yield from rotate_pin_and_collect_positional_data(
            oav, smargon, rotation_points, omega_high_limit
        )

        LOGGER.info(
            f"Run {run_num}, mid_points: {(i_positions, j_positions)}, widths {widths}, angles {omega_angles}, tips {(tip_i_positions, tip_j_positions)}"
        )

        # Filters the data captured at rotation and formats it in terms of i, j, k and angles.
        # (i_pixels,j_pixels) correspond to the (x,y) midpoint at the widest rotation, in the camera coordinate system,
        # k_pixels correspond to the distance between the midpoint and the tip of the camera at the angle orthogonal to the
        # widest rotation.
        (
            i_pixels,
            j_pixels,
            k_pixels,
            best_omega_angle,
            best_omega_angle_orthogonal,
        ) = extract_pixel_centre_values_from_rotation_data(
            i_positions, j_positions, widths, omega_angles
        )

        LOGGER.info(f"Run {run_num} centre in pixels {(i_pixels, j_pixels, k_pixels)}")
        LOGGER.info(
            f"Run {run_num} best angles {(best_omega_angle, best_omega_angle_orthogonal)}"
        )

        # Adjust waveform values to match the camera pixels.

        i_pixels *= i_scale
        j_pixels *= j_scale
        k_pixels *= j_scale
        LOGGER.info(
            f"Run {run_num} centre in pixels after scaling {(i_pixels, j_pixels, k_pixels)}"
        )

        # Adjust i_pixels if it is too far away from the pin.
        tip_i = np.median(tip_i_positions)

        i_pixels = check_i_within_bounds(
            parameters.max_tip_distance_pixels, tip_i, i_pixels
        )
        # Get the beam distance from the centre (in pixels).
        (
            beam_distance_i_pixels,
            beam_distance_j_pixels,
        ) = parameters.calculate_beam_distance(i_pixels, j_pixels)

        # Add the beam distance to the current motor position (adjusting for the changes in coordinate system
        # and the from the angle).
        motor_xyz += camera_coordinates_to_xyz(
            beam_distance_i_pixels,
            beam_distance_j_pixels,
            best_omega_angle,
            parameters.micronsPerXPixel,
            parameters.micronsPerYPixel,
        )

        LOGGER.info(f"Run {run_num} move for x, y {motor_xyz}")

        if run_num == max_run_num - 1:
            # If it's the last run we adjust the z value of the motors.
            beam_distance_k_pixels = parameters.calculate_beam_distance(
                i_pixels, k_pixels
            )[1]

            motor_xyz += camera_coordinates_to_xyz(
                0,
                beam_distance_k_pixels,
                best_omega_angle_orthogonal,
                parameters.micronsPerXPixel,
                parameters.micronsPerYPixel,
            )

        # If the x value exceeds the stub offsets, reset it to the stub offsets
        motor_xyz[1] = keep_inside_bounds(motor_xyz[1], _Y_LOWER_BOUND, _Y_UPPER_BOUND)
        motor_xyz[2] = keep_inside_bounds(motor_xyz[2], _Z_LOWER_BOUND, _Z_UPPER_BOUND)

        run_num += 1
        LOGGER.info(f"Run {run_num} move for x, y, z: {motor_xyz}")

        yield from bps.mv(
            smargon.x, motor_xyz[0], smargon.y, motor_xyz[1], smargon.z, motor_xyz[2]
        )

    # We've moved to the best x,y,z already. Now rotate to the widest pin angle.
    yield from bps.mv(smargon.omega, best_omega_angle)

    yield from bps.sleep(1)
    LOGGER.info("Finished loop centring")


if __name__ == "__main__":
    beamline = "BL03I"
    set_up_logging_handlers("INFO")
    oav = OAV(name="oav", prefix=beamline)

    smargon: Smargon = Smargon(name="smargon", prefix=beamline)
    backlight: Backlight = Backlight(name="backlight", prefix=beamline)
    parameters = OAVParameters(
        "src/artemis/unit_tests/test_OAVCentring.json",
        "src/artemis/unit_tests/test_jCameraManZoomLevels.xml",
        "src/artemis/unit_tests/test_display.configuration",
    )
    oav.wait_for_connection()
    smargon.wait_for_connection()
    RE = RunEngine()
    RE(centring_plan(oav, parameters, smargon, backlight))
