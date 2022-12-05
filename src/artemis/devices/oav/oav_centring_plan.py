import math

import bluesky.plan_stubs as bps
import numpy as np
from bluesky.run_engine import RunEngine

from artemis.devices.backlight import Backlight
from artemis.devices.motors import I03Smargon
from artemis.devices.oav.oav_detector import OAV, ColorMode, EdgeOutputArrayImageType
from artemis.devices.oav.oav_errors import (
    OAVError_MissingRotations,
    OAVError_NoRotationsPassValidityTest,
    OAVError_WaveformAllZero,
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
    yield from bps.abs_set(oav.mxsc.py_filename, filename, wait=True)
    yield from bps.abs_set(oav.mxsc.read_file, 1)

    # Image annotations
    yield from bps.abs_set(oav.mxsc.draw_tip, True)
    yield from bps.abs_set(oav.mxsc.draw_edges, True)

    # Use the original image type for the edge output array
    yield from bps.abs_set(oav.mxsc.output_array, EdgeOutputArrayImageType.ORIGINAL)

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

    yield from bps.abs_set(
        oav.zoom_controller.zoom,
        f"{float(parameters.zoom)}x",
        wait=True,
    )

    yield from bps.abs_set(backlight.pos, 1, wait=True)

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
    x_pos = np.where(gradient_changed)[0][0]

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

        yield from bps.abs_set(oav.mxsc.tip_x, np.where(top != 0)[0][0])
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
            yield from bps.mv(smargon.omega, current_omega + increment)

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
    x = x_positions[index_of_largest_width]
    y = y_positions[index_of_largest_width]
    best_omega_angle = omega_angles[index_of_largest_width]

    # Get the angle sufficiently orthogonal to the best omega and
    index_orthogonal_to_largest_width = indices_orthogonal_to_largest_width[-1]
    best_omega_angle_orthogonal = omega_angles[index_orthogonal_to_largest_width]

    # Store the y value which will be the magnitude in the z axis on 90 degree rotation
    z = y_positions[index_orthogonal_to_largest_width]

    # best_omega_angle_90 could be zero, which used to cause a failure - d'oh!
    if best_omega_angle_orthogonal is None:
        LOGGER.error("Unable to find loop at 2 orthogonal angles")
        return

    return x, y, z, best_omega_angle, best_omega_angle_orthogonal


def get_motor_movement_xyz(
    parameters: OAVParameters,
    x,
    y,
    z,
    tip_x_positions,
    indices_orthogonal_to_largest_width,
    best_omega_angle,
    best_omega_angle_orthogonal,
    last_run,
    x_size,
    y_size,
    current_motor_xyz,
):
    """
    Gets the x,y,z values the motor should move to (microns).
    """

    # extract the microns per pixel of the zoom level of the camera
    parameters.load_microns_per_pixel(parameters.zoom)

    # get the max tip distance in pixels
    max_tip_distance_pixels = parameters.max_tip_distance / parameters.micronsPerXPixel

    # we need to store the tips of the angles orthogonal-ish to the best angle
    orthogonal_tips_x = tip_x_positions[indices_orthogonal_to_largest_width]
    # get the average tip distance of the orthogonal rotations
    tip_x = np.median(orthogonal_tips_x)

    # If x exceeds the max tip distance then set it to the max tip distance.
    # This is necessary as some users send in wierd loops for which the differential method isn't
    # functional. OAV centring only needs to get in the right ballpark so Xray centring can do its thing.
    tip_distance_pixels = x - tip_x
    if tip_distance_pixels > max_tip_distance_pixels:
        LOGGER.warn(
            f"x={x} exceeds maximum tip distance {max_tip_distance_pixels}, using setting x within the max tip distance"
        )
        x = max_tip_distance_pixels + tip_x

    # get the scales of the image in microns, and the distance in microns to the beam centre location

    x_scale, y_scale = get_scale(x_size, y_size)
    x_move, y_move = calculate_beam_distance_in_microns(
        parameters, int(x * x_scale), int(y * y_scale)
    )

    # convert the distance in microns to motor incremements
    x_y_z_move = distance_from_beam_centre_to_motor_coords(
        x_move, y_move, best_omega_angle
    )

    # it's the last run then also move calculate the motor coordinates to take the orthogonal angle into account.
    if last_run:
        x_move, z_move = calculate_beam_distance_in_microns(
            parameters, int(x * x_scale), int(z * y_scale)
        )
    else:
        z_move = 0

    # This will be 0 if z_move is 0
    x_y_z_move_2 = distance_from_beam_centre_to_motor_coords(
        0, z_move, best_omega_angle_orthogonal
    )

    new_x, new_y, new_z = tuple(current_motor_xyz + x_y_z_move + x_y_z_move_2)
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

        (
            index_of_largest_width,
            indices_orthogonal_to_largest_width,
        ) = find_widest_point_and_orthogonal_point(
            x_positions, y_positions, widths, omega_angles
        )
        print("2")

        (
            x,
            y,
            z,
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

        x_size = yield from bps.rd(oav.snapshot.x_size_pv)
        y_size = yield from bps.rd(oav.snapshot.y_size_pv)

        current_motor_xyz = np.array(
            [
                (yield from bps.rd(smargon.x)),
                (yield from bps.rd(smargon.y)),
                (yield from bps.rd(smargon.z)),
            ]
        )

        print("4")
        new_x, new_y, new_z = get_motor_movement_xyz(
            parameters,
            x,
            y,
            z,
            tip_x_positions,
            indices_orthogonal_to_largest_width,
            best_omega_angle,
            best_omega_angle_orthogonal,
            run_num == max_run_num - 1,
            x_size,
            y_size,
            current_motor_xyz,
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

        # Now move loop to cross hair, converting microns to mm
        yield from bps.mv(smargon.x, new_x * 1e-3)
        print("5.x")
        yield from bps.mv(smargon.y, new_y * 1e-3)
        print("5.y")
        yield from bps.mv(smargon.z, new_z * 1e-3)
        print("5.z")
        print(6)

    # We've moved to the best x,y,z already. Now rotate to the largest bulge.
    yield from bps.mv(smargon.omega, best_omega_angle)
    print("\n\n\n\nBEST OMEGA ANGLE:", best_omega_angle)
    LOGGER.info("exiting OAVCentre")


def calculate_beam_distance_in_microns(parameters: OAVParameters, x, y):

    parameters._extract_beam_position()
    y_to_move = y - parameters.beam_centre_y
    x_to_move = parameters.beam_centre_x - x
    x_microns = int(x_to_move * parameters.micronsPerXPixel)
    y_microns = int(y_to_move * parameters.micronsPerYPixel)
    return (x_microns, y_microns)


def distance_from_beam_centre_to_motor_coords(horizontal, vertical, omega):
    """
    Converts micron measurements from pixels into to (x, y, z) motor coordinates. For an overview of the
    coordinate system for I03 see https://github.com/DiamondLightSource/python-artemis/wiki/Gridscan-Coordinate-System.

    This is designed for phase 1 mx, with the hardware located to the right of the beam, and the z axis is
    perpendicular to the beam and normal to the rotational plane of the omega axis. When the x axis is vertical
    then the y axis is anti-parallel to the beam direction.
    By definition, when omega = 0, the z axis will be positive in the vertical direction and a positive omega
    movement will rotate clockwise when looking at the viewed down x-axis. This is standard in
    crystallography.
    """
    x = -horizontal
    angle = math.radians(omega)
    cosine = math.cos(angle)
    """
    These calculations are done as though we are looking at the back of
    the gonio, with the beam coming from the left. They follow the
    mathematical convention that Z +ve goes right, Y +ve goes vertically
    up. X +ve is away from the gonio (away from you). This is NOT the
    standard phase I convention.
    """
    sine = math.sin(angle)
    z = vertical * sine
    y = vertical * cosine
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
    below_lower = value < lower_bound
    above_upper = value > upper_bound

    return (
        below_lower * lower_bound
        + above_upper * upper_bound
        + (not above_upper and not below_lower) * value
    )


if __name__ == "__main__":

    def plot_top_bottom(oav: OAV, parameters, smargon, backlight):
        import matplotlib.pyplot as plt

        top = yield from bps.rd(oav.mxsc.top)
        bottom = yield from bps.rd(oav.mxsc.bottom)
        top = np.array(top)
        bottom = np.array(bottom)
        print(top)
        print(bottom)
        plt.plot(top)
        plt.plot(bottom)
        plt.show()
        yield from centring_plan(oav, parameters, smargon, backlight)

    SIM_BEAMLINE = "BL03S"
    oav = OAV(name="oav", prefix=SIM_BEAMLINE)
    smargon = I03Smargon(name="smargon", prefix=SIM_BEAMLINE + "-MO-SGON-01:")
    backlight = Backlight(name="backlight", prefix=SIM_BEAMLINE)
    parameters = OAVParameters(
        "src/artemis/devices/unit_tests/test_OAVCentring.json",
        "src/artemis/devices/unit_tests/test_jCameraManZoomLevels.xml",
        "src/artemis/devices/unit_tests/test_display.configuration",
    )
    oav.wait_for_connection()
    smargon.wait_for_connection()
    RE = RunEngine()
    RE(centring_plan(oav, parameters, smargon, backlight))
    # RE(plot_top_bottom(oav, parameters, smargon, backlight))
