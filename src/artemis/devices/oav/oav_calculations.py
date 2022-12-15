from typing import Tuple

import numpy as np

from artemis.devices.oav.oav_errors import (
    OAVError_MissingRotations,
    OAVError_NoRotationsPassValidityTest,
)
from artemis.log import LOGGER


def smooth(y):
    """
    Remove noise from waveform using a convolution.

    Args:
        y (np.ndarray): waveform to be smoothed.
    Returns:
        y_smooth (np.ndarray): y with noise removed.
    """

    # the smoothing window is set to 50 on i03
    smoothing_window = 50
    box = np.ones(smoothing_window) / smoothing_window
    y_smooth = np.convolve(y, box, mode="same")
    return y_smooth


def find_midpoint(top, bottom):
    """
    Finds the midpoint from MXSC edge PVs. The midpoint is considered the centre of the first
    bulge in the waveforms. This will correspond to the pin where the sample is located.

    Args:
        top (np.ndarray): The waveform corresponding to the top of the pin.
        bottom (np.ndarray): The waveform corresponding to the bottom of the pin.
    Returns:
        x_pixel (int): The x position of the located centre (in pixels).
        y_pixel (int): The y position of the located centre (in pixels).
        width (int): The width of the pin at the midpoint (in pixels).
    """

    # Widths between top and bottom.
    widths = bottom - top

    # The line going down the middle of the waveform.
    middle_line = (bottom + top) * 0.5

    smoothed_width = smooth(widths)
    first_derivative = np.gradient(smoothed_width)

    # The derivative introduces more noise, so another application of smooth is neccessary.
    # The gradient is reversed prior since a new index has been introduced in smoothing, that is
    # negated by smoothing in the reversed array.
    reversed_derivative = first_derivative[::-1]
    reversed_grad = smooth(reversed_derivative)
    grad = reversed_grad[::-1]

    # np.sign gives us the positions where the gradient is positive and negative.
    # Taking the diff of th/at gives us an array with all 0's apart from the places
    # sign of the gradient went from -1 -> 1 or 1 -> -1.
    # Indices are -1 for decreasing width, +1 for increasing width.
    increasing_or_decreasing = np.sign(grad)

    # Taking the difference will give us an array with -2/2 for the places the gradient where the gradient
    # went from negative->positive/postitive->negative, 0 where it didn't change, and -1 where the gradient goes from 0->1
    # at the pin tip.
    gradient_changed = np.diff(increasing_or_decreasing)

    # np.where will give all non-zero indices: the indices where the gradient changed.
    # We take the 0th element as the x pos since it's the first place where the gradient changed, indicating a bulge.
    stationary_points = np.where(gradient_changed)[0]

    # We'll have one stationary point before the midpoint.
    x_pixel = stationary_points[1]

    y_pixel = middle_line[int(x_pixel)]
    width = widths[int(x_pixel)]
    return (x_pixel, y_pixel, width)


def get_rotation_increment(rotations: int, omega: int, high_limit: int) -> float:
    """
    By default we'll rotate clockwise (viewing the goniometer from the front), but if we
    can't rotate 180 degrees clockwise without exceeding the high_limit threshold then
    the goniometer rotates in the anticlockwise direction.

    Args:
        rotations (int): The number of rotations we want to add up to 180/-180
        omega (int): The current omega angle of the smargon.
        high_limit (int): The maximum allowed angle we want the smargon omega to have.
    Returns:
        The inrement we should rotate omega by.
    """

    # number of degrees to rotate to
    increment = 180.0 / rotations

    # if the rotation threshhold would be exceeded flip the rotation direction
    if omega + 180 > high_limit:
        increment = -increment

    return increment


def filter_rotation_data(
    x_positions: np.ndarray,
    y_positions: np.ndarray,
    widths: np.ndarray,
    omega_angles: np.ndarray,
    acceptable_x_difference=100,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Filters out outlier positions - those for which the x value of the midpoint unreasonably differs from the median of the x values at other rotations.

    Args:
        x_positions (numpy.ndarray): Array where the i-th element corresponds to the x value (in pixels) of the midpoint at rotation i.
        y_positions (numpy.ndarray): Array where the i-th element corresponds to the y value (in pixels) of the midpoint at rotation i.
        widths (numpy.ndarray): Array where the i-th element corresponds to the pin width (in pixels) of the midpoint at rotation i.
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
    outlier_x_positions = np.where(
        abs(x_positions - x_median) > acceptable_x_difference
    )[0]
    x_positions_filtered = np.delete(x_positions, outlier_x_positions)
    y_positions_filtered = np.delete(y_positions, outlier_x_positions)
    widths_filtered = np.delete(widths, outlier_x_positions)
    omega_angles_filtered = np.delete(omega_angles, outlier_x_positions)

    if not widths_filtered.size:
        raise OAVError_NoRotationsPassValidityTest(
            "No rotations pass the validity test."
        )

    return (
        x_positions_filtered,
        y_positions_filtered,
        widths_filtered,
        omega_angles_filtered,
    )


def check_x_within_bounds(
    max_tip_distance_pixels: int, tip_x: int, x_pixels: int
) -> int:
    """
    Checks if x_pixels exceeds max tip distance (in pixels), if so returns max_tip_distance, else x_pixels.
    This is necessary as some users send in wierd loops for which the differential method isn't functional.
    OAV centring only needs to get in the right ballpark so Xray centring can do its thing.
    """

    tip_distance_pixels = x_pixels - tip_x
    if tip_distance_pixels > max_tip_distance_pixels:
        LOGGER.warn(
            f"x_pixels={x_pixels} exceeds maximum tip distance {max_tip_distance_pixels}, using setting x_pixels within the max tip distance"
        )
        x_pixels = max_tip_distance_pixels + tip_x
    return x_pixels


def extract_coordinates_from_rotation_data(
    x_positions: np.ndarray,
    y_positions: np.ndarray,
    widths: np.ndarray,
    omega_angles: np.ndarray,
) -> Tuple[int, int, int, float, float]:
    """
    Takes the obtained midpoints x_positions, y_positions, the pin widths, omega_angles from the rotations
    and returns x, y, z, widest angle, and the angle orthogonal to it.

    Args:
        x_positions (numpy.ndarray): Array where the i-th element corresponds to the x value (in pixels) of the midpoint at rotation i.
        y_positions (numpy.ndarray): Array where the i-th element corresponds to the y value (in pixels) of the midpoint at rotation i.
        widths (numpy.ndarray): Array where the i-th element corresponds to the pin width (in pixels) of the midpoint at rotation i.
        omega_angles (numpy.ndarray): Array where the i-th element corresponds to the omega angle at rotation i.
    Returns:
        x_pixels (int): The x value (in pixels) of the midpoint when omega is equal to widest_omega_angle
        y_pixels (int): The y value (in pixels) of the midpoint when omega is equal to widest_omega_angle
        z_pixels (int): The y value (in pixels) of the midpoint when omega is equal to widest_omega_angle_orthogonal
        widest_omega_angle (float): The value of omega where the pin is widest in the image.
        widest_omega_angle_orthogonal (float): The value of omega orthogonal to the angle where the pin is widest in the image.
    """

    (
        index_of_largest_width,
        indices_orthogonal_to_largest_width,
    ) = find_widest_point_and_orthogonal_point(
        x_positions, y_positions, widths, omega_angles
    )

    x_pixels = int(x_positions[index_of_largest_width])
    y_pixels = int(y_positions[index_of_largest_width])

    widest_omega_angle = float(omega_angles[index_of_largest_width])

    # Get the angle sufficiently orthogonal to the omega where the pin is widest
    index_orthogonal_to_largest_width = indices_orthogonal_to_largest_width[-1]
    widest_omega_angle_orthogonal = float(
        omega_angles[index_orthogonal_to_largest_width]
    )

    # Store the y value which will be the magnitude in the z axis on 90 degree rotation
    z_pixels = int(y_positions[index_orthogonal_to_largest_width])

    #
    if widest_omega_angle_orthogonal is None:
        LOGGER.error("Unable to find loop at 2 orthogonal angles")
        return

    return (
        x_pixels,
        y_pixels,
        z_pixels,
        widest_omega_angle,
        widest_omega_angle_orthogonal,
    )


def camera_coordinates_to_xyz(
    horizontal: float,
    vertical: float,
    omega: float,
    microns_per_x_pixel: float,
    microns_per_y_pixel: float,
) -> np.ndarray:
    """
    Converts from (horizontal,vertical) pixel measurements from the OAV camera into to (x, y, z) motor coordinates in millmeters.
    For an overview of the coordinate system for I03 see https://github.com/DiamondLightSource/python-artemis/wiki/Gridscan-Coordinate-System.

    Args:
        horizontal (float): A x value from the camera in pixels.
        vertical (float): A y value from the camera in pixels.
        omega (float): The omega angle of the smargon that the horizontal, vertical measurements were obtained at.
        microns_per_x_pixel (float): The number of microns per x pixel, adjusted for the zoom level horizontal was measured at.
        microns_per_y_pixel (float): The number of microns per y pixel, adjusted for the zoom level vertical was measured at.
    """
    # Convert the vertical and horizontal into mm
    vertical *= microns_per_x_pixel * 1e-3
    horizontal *= microns_per_y_pixel * 1e-3

    # +ve x in the OAV camera becomes -ve x in the smargon motors
    x = -horizontal

    # Rotating the camera causes the position on the vertical horizontal to change by raising or lowering the centre.
    # We can negate this change by multiplying sin and cosine of the omega.
    radians = np.radians(omega)
    cosine = np.cos(radians)
    sine = np.sin(radians)

    # +ve y in the OAV camera becomes -ve y in the smargon motors/
    y = -vertical * cosine

    z = vertical * sine
    return np.array([x, y, z], dtype=np.float64)


def keep_inside_bounds(value: float, lower_bound: float, upper_bound: float) -> float:
    """
    If value is above an upper bound then the upper bound is returned.
    If value is below a lower bound then the lower bound is returned.
    If value is within bounds then the value is returned.

    Args:
        value (float): The value being checked against bounds.
        lower_bound (float): The lower bound.
        lower_bound (float): The upper bound.
    """
    if value < lower_bound:
        return lower_bound
    if value > upper_bound:
        return upper_bound
    return value


def find_widest_point_and_orthogonal_point(
    x_positions: np.ndarray,
    y_positions: np.ndarray,
    widths: np.ndarray,
    omega_angles: np.ndarray,
) -> Tuple[int, np.ndarray]:
    """
    Find the index of the rotation where the pin was widest in the camera, and the indices of rotations orthogonal to it.

    Args: Lists of values taken, the i-th value of the list is the i-th point sampled:
            x_positions (numpy.ndarray): Array where the i-th element corresponds to the x value (in pixels) of the midpoint at rotation i.
            y_positions (numpy.ndarray): Array where the i-th element corresponds to the y value (in pixels) of the midpoint at rotation i.
            widths (numpy.ndarray): Array where the i-th element corresponds to the pin width (in pixels) of the midpoint at rotation i.
            omega_angles (numpy.ndarray): Array where the i-th element corresponds to the omega angle at rotation i.
    Returns: The index of the sample which had the widest pin as an int, and the indices orthogonal to that as a numpy array.
    """

    (
        x_positions_filtered,
        y_positions_filtered,
        widths_filtered,
        omega_angles_filtered,
    ) = filter_rotation_data(x_positions, y_positions, widths, omega_angles)

    # Find omega for face-on position: where bulge was widest
    index_of_largest_width_filtered = widths_filtered.argmax()

    index_of_largest_width = int(
        np.where(
            omega_angles == omega_angles_filtered[index_of_largest_width_filtered]
        )[0]
    )

    # find largest width index in original unfiltered list
    widest_omega_angle = omega_angles[index_of_largest_width]
    # Find the best angles orthogonal to the best_omega_angle
    try:
        indices_orthogonal_to_largest_width_filtered = np.where(
            (85 < abs(omega_angles_filtered - widest_omega_angle))
            & (abs(omega_angles_filtered - widest_omega_angle) < 95)
        )[0]
    except (IndexError):
        raise OAVError_MissingRotations("Unable to find loop at 2 orthogonal angles")

    indices_orthogonal_to_largest_width = np.array([], dtype=np.uint32)
    for angle in omega_angles_filtered[indices_orthogonal_to_largest_width_filtered]:
        indices_orthogonal_to_largest_width = np.append(
            indices_orthogonal_to_largest_width, np.where(omega_angles == angle)[0]
        )

    return index_of_largest_width, indices_orthogonal_to_largest_width
