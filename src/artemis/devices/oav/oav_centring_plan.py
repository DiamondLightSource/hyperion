import math

import bluesky.plan_stubs as bps
import numpy as np
from bluesky.run_engine import RunEngine

from artemis.devices.backlight import Backlight
from artemis.devices.I03Smargon import I03Smargon
from artemis.devices.oav.oav_detector import OAV, ColorMode, EdgeOutputArrayImageType
from artemis.devices.oav.oav_errors import (
    OAVError_MissingRotations,
    OAVError_NoRotationsPassValidityTest,
    OAVError_WaveformAllZero,
    OAVError_ZoomLevelNotFound,
)
from artemis.devices.oav.oav_parameters import OAVParameters
from artemis.log import LOGGER
from artemis.parameters import SIM_BEAMLINE

# from bluesky import RunEngine


# Scaling factors used in GDA. We should look into improving by not using these.
_X_SCALING_FACTOR = 1024
_Y_SCALING_FACTOR = 768

# Z and Y bounds are hardcoded into GDA (we don't want to exceed them). We should look
# at streamlining this
_Z_LOWER_BOUND = _Y_LOWER_BOUND = -1500
_Z_UPPER_BOUND = _Y_UPPER_BOUND = 1500

# The smargon can  rotate indefinitely, so the [high/low]_limit_travel is set as 0 to
# reflect this. Despite this, Neil would like to have omega to oscillate so we will
# hard code limits so gridscans will switch rotation directions and |omega| will stay pretty low.
_DESIRED_HIGH_LIMIT = 181
_DESIRED_LOW_LIMIT = -181


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


def smooth(y):
    "Remove noise from waveform."

    # the smoothing window is set to 50 on i03
    smoothing_window = 50
    box = np.ones(smoothing_window) / smoothing_window
    y_smooth = np.convolve(y, box, mode="same")
    return y_smooth


def find_midpoint(top, bottom):
    """
    Finds the midpoint from edge PVs. The midpoint is considered the centre of the first
    bulge in the waveforms. This will correspond to the pin where the sample is located.
    """

    # widths between top and bottom
    widths = bottom - top

    # line going through the middle
    mid_line = (bottom + top) * 0.5

    smoothed_width = smooth(widths)  # smoothed widths
    first_derivative = np.gradient(smoothed_width)  # gradient

    # the derivative introduces more noise, so another application of smooth is neccessary
    # the gradient is reversed prior to since a new index has been introduced in smoothing, that is
    # negated by smoothing in the reversed array
    reversed_deriv = first_derivative[::-1]
    reversed_grad = smooth(reversed_deriv)
    grad = reversed_grad[::-1]

    # np.sign gives us the positions where the gradient is positive and negative.
    # Taking the diff of th/at gives us an array with all 0's apart from the places
    # sign of the gradient went from -1 -> 1 or 1 -> -1.
    # indices are -1 for decreasing width, +1 for increasing width
    increasing_or_decreasing = np.sign(grad)

    # Taking the difference will give us an array with -2/2 for the places the gradient where the gradient
    # went from negative->positive/postitive->negative, and 0 where it didn't change
    gradient_changed = np.diff(increasing_or_decreasing)

    # np.where will give all non-zero indices: the indices where the gradient changed.
    # We take the 0th element as the x pos since it's the first place where the gradient changed, indicating a bulge.
    stationary_points = np.where(gradient_changed)[0]

    # We'll have one stationary point before the midpoint.
    x_pos = stationary_points[1]

    y_pos = mid_line[int(x_pos)]
    diff_at_x_pos = widths[int(x_pos)]
    return (x_pos, y_pos, diff_at_x_pos, mid_line)


def get_rotation_increment(rotations: int, omega: int, high_limit: int) -> float:
    """
    By default we'll rotate clockwise (viewing the goniometer from the front),
    but if we can't rotate 180 degrees clockwise without exceeding the threshold
    then the goniometer rotates in the anticlockwise direction.
    """

    # number of degrees to rotate to
    increment = 180.0 / rotations

    # if the rotation threshhold would be exceeded flip the rotation direction
    print("\n\n\n\nOMEGA:", omega)
    if omega + 180 > high_limit:
        increment = -increment

    return increment


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
            mid_lines: the waveform going between the top and bottom waveforms
            tip_x_positions: the measured x tip at a given rotation
            tip_y_positions: the measured y tip at a given rotation
    """
    smargon.wait_for_connection()
    current_omega = yield from bps.rd(smargon.omega)

    # The angle to rotate by on each iteration
    increment = get_rotation_increment(rotations, current_omega, omega_high_limit)
    print("\n\n\nnew_increment:", increment)

    # Arrays to hold positions data of the pin at each rotation
    # These need to be np arrays for their use in centring
    print("0.1")

    x_positions = np.array([], dtype=np.int32)
    y_positions = np.array([], dtype=np.int32)
    widths = np.array([], dtype=np.int32)
    omega_angles = np.array([], dtype=np.int32)
    mid_lines = np.array([], dtype=np.int32)
    tip_x_positions = np.array([], dtype=np.int32)
    tip_y_positions = np.array([], dtype=np.int32)

    for i in range(rotations):
        print(f"0.1{i+1}")
        current_omega = yield from bps.rd(smargon.omega)
        top = np.array((yield from bps.rd(oav.mxsc.top)))

        bottom = np.array((yield from bps.rd(oav.mxsc.bottom)))
        tip_x = yield from bps.rd(oav.mxsc.tip_x)
        tip_y = yield from bps.rd(oav.mxsc.tip_y)

        for waveform in (top, bottom):
            if np.all(waveform == 0):
                raise OAVError_WaveformAllZero(
                    f"error at rotation {current_omega}, one of the waveforms is all 0"
                )

        (x, y, width, mid_line) = find_midpoint(top, bottom)
        # Build arrays of edges and width, and store corresponding gonomega
        x_positions = np.append(x_positions, x)
        y_positions = np.append(y_positions, y)
        widths = np.append(widths, width)
        omega_angles = np.append(omega_angles, current_omega)
        mid_lines = np.append(mid_lines, mid_line)
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
        mid_lines,
        tip_x_positions,
        tip_y_positions,
    )


def filter_rotation_data(
    x_positions,
    y_positions,
    widths,
    omega_angles,
    acceptable_x_difference=100,
):
    """
    Filters out outlier positions, and zero points.

    Args:
        x_positions: the x positions of centres
        y_positions: the y positions of centres
        widths: the widths between the top and bottom waveforms at the centre point
        omega_angles: the angle of the goniometer at which the measurement was taken
        acceptable_x_difference: the acceptable difference between the average value of x and
            any individual value of x. We don't want to use exceptional positions for calculation.
    Returns:
        x_positions_filtered: the x_positions with outliers filtered out
        y_positions_filtered: the y_positions with outliers filtered out
        widths_filtered: the widths with outliers filtered out
        omega_angles_filtered: the omega_angles with outliers filtered out
    """
    # find the average of the non zero elements of the array
    x_median = np.median(x_positions)

    # filter out outliers
    outlier_x_positions = np.where(x_positions - x_median > acceptable_x_difference)[0]
    widths_filtered = np.delete(widths, outlier_x_positions)
    omega_angles_filtered = np.delete(omega_angles, outlier_x_positions)

    if not widths_filtered.size:
        raise OAVError_NoRotationsPassValidityTest(
            "No rotations pass the validity test."
        )

    return (
        widths_filtered,
        omega_angles_filtered,
    )


def find_widest_point_and_orthogonal_point(
    x_positions, y_positions, widths, omega_angles
):
    """
    Find the widest point from the sampled positions, and the angles orthogonal to this.

    Args: Lists of values taken, the ith value of the list is the ith point sampled:
            x_positions: the x positions of centres
            y_positions: the y positions of centres
            widths: the widths between the top and bottom waveforms at the centre point
            omega_angles: the angle of the goniometer at which the measurement was taken
            mid_lines: the waveform going between the top and bottom waveforms
            tip_x_positions: the measured x tip at a given rotation
            tip_y_positions: the measured y tip at a given rotation
    Returns: The index  of the sample which is wildest.
    """

    (
        widths_filtered,
        omega_angles_filtered,
    ) = filter_rotation_data(x_positions, y_positions, widths, omega_angles)

    # Find omega for face-on position: where bulge was widest
    index_of_largest_width_filtered = widths_filtered.argmax()

    # find largest width index in original unfiltered list
    best_omega_angle = omega_angles_filtered[index_of_largest_width_filtered]
    index_of_largest_width = np.where(
        omega_angles == omega_angles_filtered[index_of_largest_width_filtered]
    )[0]

    # Find the best angles orthogonal to the best_omega_angle
    try:
        indices_orthogonal_to_largest_width_filtered = np.where(
            (85 < abs(omega_angles_filtered - best_omega_angle))
            & (abs(omega_angles_filtered - best_omega_angle) < 95)
        )[0]
    except (IndexError):
        raise OAVError_MissingRotations("Unable to find loop at 2 orthogonal angles")

    indices_orthogonal_to_largest_width = np.array([], dtype=np.uint32)
    for angle in omega_angles_filtered[indices_orthogonal_to_largest_width_filtered]:
        indices_orthogonal_to_largest_width = np.append(
            indices_orthogonal_to_largest_width, np.where(omega_angles == angle)[0]
        )

    return index_of_largest_width, indices_orthogonal_to_largest_width


def get_scale(x_size, y_size):
    """
    Returns the scale of the image. The standard calculation for the image is based
    on a size of (1024, 768) so we require these scaling factors.
    Args:
        x_size: the x size of the image, in pixels
        y_size: the y size of the image, in pixels
    Returns:
        The (x,y) where x, y is the dimensions of the image in microns
    """
    return _X_SCALING_FACTOR / x_size, _Y_SCALING_FACTOR / y_size


def extract_coordinates_from_rotation_data(
    x_positions,
    y_positions,
    index_of_largest_width,
    indices_orthogonal_to_largest_width,
    omega_angles,
):
    """
    Takes the rotations being used and gets the neccessary data in terms of x,y,z and angles.
    This is much nicer to read.
    """
    x_pixels = x_positions[index_of_largest_width]
    print("YPOSITIONS", y_positions)
    y_pixels = y_positions[index_of_largest_width]

    best_omega_angle = float(omega_angles[index_of_largest_width])

    # Get the angle sufficiently orthogonal to the best omega and
    index_orthogonal_to_largest_width = indices_orthogonal_to_largest_width[-1]
    best_omega_angle_orthogonal = float(omega_angles[index_orthogonal_to_largest_width])

    # Store the y value which will be the magnitude in the z axis on 90 degree rotation
    z_pixels = y_positions[index_orthogonal_to_largest_width]

    # best_omega_angle_90 could be zero, which used to cause a failure - d'oh!
    if best_omega_angle_orthogonal is None:
        LOGGER.error("Unable to find loop at 2 orthogonal angles")
        return

    return x_pixels, y_pixels, z_pixels, best_omega_angle, best_omega_angle_orthogonal


def check_x_within_bounds(parameters: OAVParameters, tip_x, x_pixels):
    # extract the microns per pixel of the zoom level of the camera
    parameters.load_microns_per_pixel(parameters.zoom)

    # get the max tip distance in pixels
    max_tip_distance_pixels = parameters.max_tip_distance / parameters.micronsPerXPixel

    # If x exceeds the max tip distance then set it to the max tip distance.
    # This is necessary as some users send in wierd loops for which the differential method isn't
    # functional. OAV centring only needs to get in the right ballpark so Xray centring can do its thing.
    tip_distance_pixels = x_pixels - tip_x
    if tip_distance_pixels > max_tip_distance_pixels:
        LOGGER.warn(
            f"x_pixels={x_pixels} exceeds maximum tip distance {max_tip_distance_pixels}, using setting x_pixels within the max tip distance"
        )
        x_pixels = max_tip_distance_pixels + tip_x
    return x_pixels


def get_motor_movement_xyz(
    parameters: OAVParameters,
    current_motor_xyz,
    x_pixels,
    y_pixels,
    z_pixels,
    best_omega_angle,
    best_omega_angle_orthogonal,
    last_run,
    x_scale,
    y_scale,
):
    """
    Gets the x,y,z values the motor should move to (microns).
    """

    # Get the scales of the image in microns, and the distance in microns to the beam centre location.
    x_move, y_move = calculate_beam_distance(
        parameters, int(x_pixels * x_scale), int(y_pixels * y_scale), flip_vertical=True
    )

    # convert the distance in microns to motor incremements
    x_y_z_move = distance_from_beam_centre_to_motor_coords(
        x_move, y_move, best_omega_angle
    )

    # It's the last run then also move calculate the motor coordinates taking
    if last_run:
        x_move, z_move = calculate_beam_distance(
            parameters,
            int(x_pixels * x_scale),
            int(z_pixels * y_scale),
            flip_vertical=True,
        )
        x_y_z_move += distance_from_beam_centre_to_motor_coords(
            0, z_move, best_omega_angle_orthogonal
        )

    new_x, new_y, new_z = tuple(current_motor_xyz + x_y_z_move)
    print("new_XYZ (before bounding):", new_x, new_y, new_z)

    new_y = keep_inside_bounds(new_y, _Y_LOWER_BOUND, _Y_UPPER_BOUND)
    new_z = keep_inside_bounds(new_z, _Z_LOWER_BOUND, _Z_UPPER_BOUND)
    return new_x, new_y, new_z


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

    yield from bps.wait()

    # Set relevant PVs to whatever the config dictates
    yield from pre_centring_setup_oav(oav, backlight, parameters)

    # If omega  can rotate indefinitely (indicated by high_limit_travel=0), we set the hard coded limit
    omega_high_limit = yield from bps.rd(smargon.omega.high_limit_travel)
    if not omega_high_limit:
        omega_high_limit = _DESIRED_HIGH_LIMIT

    # we attempt to find the centre `max_run_num` times.
    run_num = 0
    while run_num < max_run_num:

        # do omega spin and harvest edge information
        (
            x_positions,
            y_positions,
            widths,
            omega_angles,
            mid_lines,
            tip_x_positions,
            tip_y_positions,
        ) = yield from rotate_pin_and_collect_positional_data(
            oav, smargon, rotation_points, omega_high_limit
        )
        print("1")
        print("OMEGA ANGLES", omega_angles)

        (
            index_of_largest_width,
            indices_orthogonal_to_largest_width,
        ) = find_widest_point_and_orthogonal_point(
            x_positions, y_positions, widths, omega_angles
        )
        print("2")

        (
            x_pixels,
            y_pixels,
            z_pixels,
            best_omega_angle,
            best_omega_angle_orthogonal,
        ) = extract_coordinates_from_rotation_data(
            x_positions,
            y_positions,
            index_of_largest_width,
            indices_orthogonal_to_largest_width,
            omega_angles,
        )
        print("3")
        print("BEST OMEGA ANGLE", best_omega_angle)

        # get the average tip distance of the orthogonal rotations, check if our
        # x value exceeds the
        tip_x = np.median(tip_x_positions[indices_orthogonal_to_largest_width])
        x_pixels = check_x_within_bounds(parameters, tip_x, x_pixels)

        x_size = yield from bps.rd(oav.snapshot.x_size_pv)
        y_size = yield from bps.rd(oav.snapshot.y_size_pv)
        x_scale, y_scale = get_scale(x_size, y_size)

        # Smargon levels are in mm, we convert them to microns here
        current_motor_xyz = (
            np.array(
                [
                    (yield from bps.rd(smargon.x)),
                    (yield from bps.rd(smargon.y)),
                    (yield from bps.rd(smargon.z)),
                ]
            )
            * 1e3
        )
        print("XPIXELS", x_pixels)
        print("YPIXELS", y_pixels)

        print("4")
        new_x, new_y, new_z = get_motor_movement_xyz(
            parameters,
            current_motor_xyz,
            x_pixels,
            y_pixels,
            z_pixels,
            best_omega_angle,
            best_omega_angle_orthogonal,
            run_num == max_run_num - 1,
            x_scale,
            y_scale,
        )
        print("5")

        print(f"\nrun {run_num} result:")
        run_num += 1
        print("current x: ", (yield from bps.rd(smargon.x)))
        print("current y: ", (yield from bps.rd(smargon.y)))
        print("current z: ", (yield from bps.rd(smargon.z)))
        print("new x    : ", new_x * 1e-3)
        print("new y    : ", new_y * 1e-3)
        print("new z    : ", new_z * 1e-3)

        # Now move loop to cross hair
        yield from bps.mv(
            smargon.x, new_x * 1e-3, smargon.y, new_y * 1e-3, smargon.z, new_z * 1e-3
        )
        print(6)

    # We've moved to the best x,y,z already. Now rotate to the largest bulge.
    yield from bps.mv(smargon.omega, best_omega_angle)
    print("\n\n\n\nBEST OMEGA ANGLE:", best_omega_angle)
    LOGGER.info("exiting OAVCentre")


def calculate_beam_distance(
    parameters: OAVParameters,
    horizontal,
    vertical,
    use_microns=True,
    flip_vertical=False,
):
    """
    Calculates the distance between the beam centre and the beam centre and a given (horizontal, vertical),
    optionally returning the result in microns.
    """

    parameters._extract_beam_position()

    # The waveform is flipped from the standard x,y of the image.
    # This means we need to negate the y to have the distance in the standard image coordinate system.
    if flip_vertical:
        vertical = _Y_SCALING_FACTOR - vertical

    horizontal_to_move = parameters.beam_centre_x - horizontal
    vertical_to_move = parameters.beam_centre_y - vertical

    if use_microns:
        horizontal_to_move = int(horizontal_to_move * parameters.micronsPerXPixel)
        print("VERTICAL TO MOVE:", vertical_to_move)
        vertical_to_move = int(vertical_to_move * parameters.micronsPerYPixel)
        print("VERTICAL TO MOVE_microns:", vertical_to_move)

    return (horizontal_to_move, vertical_to_move)


def distance_from_beam_centre_to_motor_coords(horizontal, vertical, omega):
    """
    Converts from (horizontal,vertical) micron measurements from the OAV camera into to (x, y, z) motor coordinates.
    For an overview of the coordinate system for I03 see https://github.com/DiamondLightSource/python-artemis/wiki/Gridscan-Coordinate-System.
    """
    # +ve x in the OAV camera becomes -ve x in the smargon motors
    x = -horizontal

    # Rotating the camera causes the position on the vertical horizontal to change by raising or lowering the centre.
    # We can negate this change by multiplying sin and cosine of the omega.
    radians = math.radians(omega)
    cosine = math.cos(radians)
    sine = math.sin(radians)
    y = -vertical

    # +ve y in the OAV camera becomes -ve y in the smargon motors/
    y = -vertical * cosine

    # The Z motor is only calculated (moved by the width of the pin when orthogonal) in the last run of the main centring loop,
    # however we still need to offset the error introduced by rotation here.
    z = -vertical * sine
    return np.array([x, y, z])


def keep_inside_bounds(value, lower_bound, upper_bound):
    """
    If value is above an upper bound then the upper bound is returned.
    If value is below a lower bound then the lower bound is returned.
    If value is within bounds then the value is returned

    Args:
        value: the value being checked against bounds
        lower_bound: the lower bound
        lower_bound: the upper bound
    """
    if value < lower_bound:
        return lower_bound
    if value > upper_bound:
        return upper_bound
    return value


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
