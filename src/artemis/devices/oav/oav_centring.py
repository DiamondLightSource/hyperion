import json
import math

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import numpy as np
from bluesky import RunEngine

from artemis.devices.backlight import Backlight
from artemis.devices.motors import I03Smargon
from artemis.devices.oav.oav_detector import (
    OAV,
    Camera,
    ColorMode,
    EdgeOutputArrayImageType,
)
from artemis.log import LOGGER

# Scaling factors used in GDA. We should look into improving by not using these.
_X_SCALING_FACTOR = 1024
_Y_SCALING_FACTOR = 768


class OAVParameters:
    def __init__(self, file, context="loopCentring"):
        self.file = file
        self.context = context

    def load_json(self):
        """
        Loads the json from the json file at self.file.
        """
        with open(f"{self.file}") as f:
            self.parameters = json.load(f)

    def load_parameters_from_json(
        self,
    ) -> None:
        """
        Load all the parameters needed on initialisation as class variables. If a variable in the json is
        liable to change throughout a run it is reloaded when needed.
        """

        self.load_json()

        self.exposure = self._extract_dict_parameter("exposure")
        self.acquire_period = self._extract_dict_parameter("acqPeriod")
        self.gain = self._extract_dict_parameter("gain")
        self.canny_edge_upper_threshold = self._extract_dict_parameter(
            "CannyEdgeUpperThreshold"
        )
        self.canny_edge_lower_threshold = self._extract_dict_parameter(
            "CannyEdgeLowerThreshold", fallback_value=5.0
        )
        self.minimum_height = self._extract_dict_parameter("minheight")
        self.zoom = self._extract_dict_parameter("zoom")
        # gets blur type, e.g. 8 = gaussianBlur, 9 = medianBlur
        self.preprocess = self._extract_dict_parameter("preprocess")
        # length scale for blur preprocessing
        self.preprocess_K_size = self._extract_dict_parameter("preProcessKSize")
        self.filename = self._extract_dict_parameter("filename")
        self.close_ksize = self._extract_dict_parameter(
            "close_ksize", fallback_value=11
        )

        self.input_plugin = self._extract_dict_parameter("oav", fallback_value="OAV")
        self.mxsc_input = self._extract_dict_parameter(
            "mxsc_input", fallback_value="CAM"
        )
        self.min_callback_time = self._extract_dict_parameter(
            "min_callback_time", fallback_value=0.08
        )

        self.direction = self._extract_dict_parameter("direction")

        self.max_tip_distance = self._extract_dict_parameter("max_tip_distance")

    def _extract_dict_parameter(self, key: str, fallback_value=None, reload_json=False):
        """
        Designed to extract parameters from the json OAVParameters.json. This will hopefully be changed in
        future, but currently we have to use the json passed in from GDA

        The json is of the form:
            {
                "parameter1": value1,
                "parameter2": value2,
                "context_name": {
                    "parameter1": value3
            }
        When we extract the parameters we want to check if the given context (stored as a class variable)
        contains a parameter, if it does we return it, if not we return the global value. If a parameter
        is not found at all then the passed in fallback_value is returned. If that isn't found then an
        error is raised.

        Args:
            key: the key of the value being extracted
            fallback_value: a value to be returned if the key is not found
            reload_json: reload the json from the file before searching for it, needed because some
                parameters can change mid operation.

        Returns: The extracted value corresponding to the key, or the fallback_value if none is found.
        """

        if reload_json:
            self.load_json()

        if self.context in self.parameters:
            if key in self.parameters[self.context]:
                return self.parameters[self.context][key]

        if key in self.parameters:
            return self.parameters[key]

        if fallback_value:
            return fallback_value

        # No fallback_value was given and the key wasn't found
        raise KeyError(
            f"Searched in {self.file} for key {key} in context {self.context} but no value was found. No fallback value was given."
        )

    def load_microns_per_pixel(self, zoom):
        zoom_levels_filename = "src/artemis/oav/microns_for_zoom_levels.json"
        f = open(zoom_levels_filename)
        json_dict = json.load(f)
        self.micronsPerXPixel = json_dict[zoom]["micronsPerXPixel"]
        self.micronsPerYPixel = json_dict[zoom]["micronsPerYPixel"]
        if self.micronsPerXPixel is None or self.micronsPerYPixel is None:
            raise KeyError(
                f"Could not find the micronsPer[X,Y]Pixel parameters in {zoom_levels_filename}."
            )


class OAVCentring:
    def __init__(self, parameters_file, display_configuration_path, beamline="BL03I"):
        self.display_configuration_path = display_configuration_path
        self.oav = OAV(name="oav", prefix=beamline + "-DI-OAV-01:")
        self.oav_camera = Camera(name="oav-camera", prefix=beamline + "-EA-OAV-01:")
        self.oav_backlight = Backlight(name="oav-backlight", prefix=beamline)
        self.oav_goniometer = I03Smargon(name="oav-goniometer", prefix="-MO-SGON-01:")
        self.oav_parameters = OAVParameters(parameters_file)
        self.oav.wait_for_connection()

    def pre_centring_setup_oav(self):
        """Setup OAV PVs with required values."""

        self.oav_parameters.load_parameters_from_json()

        yield from bps.abs_set(self.oav.colour_mode_pv, ColorMode.RGB1)
        yield from bps.abs_set(
            self.oav.acquire_period_pv, self.oav_parameters.acquire_period
        )
        yield from bps.abs_set(self.oav.exposure_pv, self.oav_parameters.exposure)
        yield from bps.abs_set(self.oav.gain_pv, self.oav_parameters.gain)

        # select which blur to apply to image
        yield from bps.abs_set(
            self.oav.preprocess_operation_pv, self.oav_parameters.preprocess
        )

        # sets length scale for blurring
        yield from bps.abs_set(
            self.oav.preprocess_ksize_pv, self.oav_parameters.preprocess_K_size
        )

        # Canny edge detect
        yield from bps.abs_set(
            self.oav.canny_lower_threshold_pv,
            self.oav_parameters.canny_edge_lower_threshold,
        )
        yield from bps.abs_set(
            self.oav.canny_upper_threshold_pv,
            self.oav_parameters.canny_edge_upper_threshold,
        )
        # "Close" morphological operation
        yield from bps.abs_set(self.oav.close_ksize_pv, self.oav_parameters.close_ksize)

        # Sample detection
        yield from bps.abs_set(
            self.oav.sample_detection_scan_direction_pv, self.oav_parameters.direction
        )
        yield from bps.abs_set(
            self.oav.sample_detection_min_tip_height_pv,
            self.oav_parameters.minimum_height,
        )

        # Connect MXSC output to MJPG input
        yield from self.start_mxsc(
            self.oav_parameters.input_plugin + "." + self.oav_parameters.mxsc_input,
            self.oav_parameters.min_callback_time,
            self.oav_parameters.filename,
        )

        yield from bps.abs_set(
            self.oav.input_pv, self.oav_parameters.input_plugin + ".MXSC"
        )

        # zoom is an integer value, stored as a float in a string so
        # we may need a .0 on the end? GDA does this with
        # zoomString = '%1.0dx' % float(zoom)
        # which seems suspicious, we may want to think about doing this in a nicer way
        yield from bps.abs_set(
            self.oav_camera.zoom, f"{float(int(self.oav_parameters.zoom))}x", wait=True
        )

        if (yield from bps.rd(self.oav_backlight.pos)) == 0:
            yield from bps.abs_set(self.oav_backlight.pos, 1, wait=True)

        """
       TODO: currently can't find the backlight brightness
        this will need to be set up after issue
        https://github.com/DiamondLightSource/python-artemis/issues/317
        is solved
         brightnessToUse = self.oav_parameters._extract_dict_parameter(
            context, "brightness"
        )

        blbrightness.moveTo(brightnessToUse)
        """

    def start_mxsc(self, input_plugin, min_callback_time, filename):
        """
        Sets PVs relevant to edge detection plugin.

        Args:
            input_plugin: link to the camera stream
            min_callback_time: the value to set the minimum callback time to
            filename: filename of the python script to detect edge waveforms from camera stream.
        Returns: None
        """
        yield from bps.abs_set(self.oav.input_plugin_pv, input_plugin)

        # Turns the area detector plugin on
        yield from bps.abs_set(self.oav.enable_callbacks_pv, 1)

        # Set the minimum time between updates of the plugin
        yield from bps.abs_set(self.oav.min_callback_time_pv, min_callback_time)

        # Stop the plugin from blocking the IOC and hogging all the CPU
        yield from bps.abs_set(self.oav.blocking_callbacks_pv, 0)

        # Set the python file to use for calculating the edge waveforms
        yield from bps.abs_set(self.oav.py_filename_pv, filename, wait=True)
        yield from bps.abs_set(self.oav.read_file_pv, 1)

        # Image annotations
        yield from bps.abs_set(self.oav.draw_tip_pv, True)
        yield from bps.abs_set(self.oav.draw_edges_pv, True)

        # Use the original image type for the edge output array
        yield from bps.abs_set(
            self.oav.output_array_pv, EdgeOutputArrayImageType.ORIGINAL
        )

    def _extract_beam_position(self):
        """

        Extracts the beam location in pixels `xCentre` `yCentre` extracted
        from the file display.configuration. The beam location is manually
        inputted by the beamline operator GDA by clicking where on screen a
        scintillator ligths up.
        """
        with open(self.display_configuration_path, "r") as f:
            file_lines = f.readlines()
            for i in range(len(file_lines)):
                if file_lines[i].startswith(
                    "zoomLevel = " + str(self.oav_parameters.zoom)
                ):
                    crosshair_x_line = file_lines[i + 1]
                    crosshair_y_line = file_lines[i + 2]
                    break

            if crosshair_x_line is None or crosshair_y_line is None:
                pass  # TODO throw error

            self.beam_centre_x = int(crosshair_x_line.split(" = ")[1])
            self.beam_centre_y = int(crosshair_y_line.split(" = ")[1])

    def get_formatted_edge_waveforms(self):
        """
        Get the waveforms from the PVs as numpy arrays.
        """
        yield from bps.rd(self.oav.top_pv)
        yield from bps.rd(self.oav.bottom_pv)

    def smooth(self, y):
        "Remove noise from waveform."

        # the smoothing window is set to 50 on i03
        smoothing_window = 50
        box = np.ones(smoothing_window) / smoothing_window
        y_smooth = np.convolve(y, box, mode="same")
        return y_smooth

    def find_midpoint(self, top, bottom):
        "Finds the midpoint from edge PVs. The midpoint is considered the place where"

        # widths between top and bottom
        widths = bottom - top

        # line going through the middle
        mid_line = (bottom + top) * 0.5

        smoothed_width = self.smooth(widths)  # smoothed widths
        first_derivative = np.gradient(smoothed_width)  # gradient

        # the derivative introduces more noise, so another application of smooth is neccessary
        # the gradient is reversed prior to since a new index has been introduced in smoothing, that is
        # negated by smoothing in the reversed array
        reversed_deriv = first_derivative[::-1]
        reversed_grad = self.smooth(reversed_deriv)
        grad = reversed_grad[::-1]

        # np.sign gives us the positions where the gradient is positive and negative.
        # Taking the diff of that gives us an array with all 0's apart from the places
        # sign of the gradient went from -1 -> 1 or 1 -> -1.
        # np.where will give all non-zero positions from the np.sign call, however it returns a singleton tuple.
        # We get the [0] index of the singleton tuple, then the [0] element of that to
        # get the first index where the gradient is 0.
        x_pos = np.where(np.diff(np.sign(grad)))[0][0]

        y_pos = mid_line[int(x_pos)]
        diff_at_x_pos = widths[int(x_pos)]
        return (x_pos, y_pos, diff_at_x_pos, mid_line)

    def extract_data_from_pvs(self):
        yield from bps.rd(self.oav_goniometer.omega)
        yield from self.get_formatted_edge_waveforms()
        yield from bps.rd(self.oav.tip_x_pv)
        yield from bps.rd(self.oav.tip_y_pv)
        yield from bps.rd(self.oav_goniometer.omega.high_limit_travel)

    def get_rotation_increment(
        self, rotations: int, omega: int, high_limit: int
    ) -> float:
        """
        By default we'll rotate clockwise (viewing the goniometer from the front),
        but if we can't rotate 180 degrees clockwise without exceeding the threshold
        then the goniometer rotates in the anticlockwise direction.
        """
        # number of degrees to rotate to
        increment = 180.0 / rotations

        # if the rotation threshhold would be exceeded flip the rotation direction
        if omega + 180 > high_limit:
            increment = -increment

        return increment

    def get_spacial_data_from_pin_at_different_rotations(self, rotations: int):
        """
        Calculate relevant spacial points at each rotation and save them in lists.

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
        self.oav_goniometer.wait_for_connection()
        current_omega, top, bottom, tip_x, tip_y, omega_limit = tuple(
            self.extract_data_from_pvs()
        )
        increment = self.get_rotation_increment(rotations, current_omega, omega_limit)

        # Arrays to hold positions data of the pin at each rotation
        # These need to be np arrays for their use in centring
        x_positions = np.array([], dtype=np.int32)
        y_positions = np.array([], dtype=np.int32)
        widths = np.array([], dtype=np.int32)
        omega_angles = np.array([], dtype=np.int32)
        mid_lines = np.array([], dtype=np.int32)
        tip_x_positions = np.array([], dtype=np.int32)
        tip_y_positions = np.array([], dtype=np.int32)

        for i in range(rotations):
            current_omega, top, bottom, tip_x, tip_y, omega_limit = tuple(
                self.extract_data_from_pvs()
            )
            (x, y, width, mid_line) = self.find_midpoint(top, bottom)

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
                yield from bps.mv(self.oav_goniometer.omega, current_omega + increment)

        yield (
            x_positions,
            y_positions,
            widths,
            omega_angles,
            mid_lines,
            tip_x_positions,
            tip_y_positions,
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

        # filter out 0 elements
        zero_x_positions = np.where(x_positions == 0)[0]
        zero_y_positions = np.where(y_positions == 0)[0]
        indices_to_remove = np.union1d(zero_x_positions, zero_y_positions)
        x_positions_filtered = np.delete(x_positions, indices_to_remove)
        y_positions_filtered = np.delete(y_positions, indices_to_remove)
        widths_filtered = np.delete(widths, indices_to_remove)
        omega_angles_filtered = np.delete(omega_angles, indices_to_remove)

        # If all arrays are 0 it means there has been a problem
        if not x_positions.size:
            LOGGER.warn("Unable to find loop - all values zero")
            return

        # find the average of the non zero elements of the array
        x_median = np.median(x_positions_filtered)

        # filter out outliers
        outlier_x_positions = np.where(x_positions_filtered - x_median < 100)[0]
        x_positions_filtered = np.delete(x_positions_filtered, outlier_x_positions)
        y_positions_filtered = np.delete(y_positions_filtered, outlier_x_positions)
        widths_filtered = np.delete(widths_filtered, outlier_x_positions)
        omega_angles_filtered = np.delete(omega_angles_filtered, outlier_x_positions)

        if not widths_filtered.size:
            LOGGER.error("Unable to find loop - no values pass validity test")
            return

        # Find omega for face-on position: where bulge was widest
        index_of_largest_width = widths_filtered.argmax()

        # find largest width index in original unfiltered list
        index_of_largest_width = widths[
            np.where(omega_angles == omega_angles_filtered[index_of_largest_width])[0]
        ]
        best_omega_angle = omega_angles[index_of_largest_width]

        # Find the best angles orthogonal to the best_omega_angle
        try:
            indices_orthogonal_to_largest_width = np.where(
                (85 < abs(omega_angles - best_omega_angle))
                & (abs(omega_angles - best_omega_angle) < 95)
            )[0]
        except (IndexError):
            errmsg = "Unable to find loop at 2 orthogonal angles"
            LOGGER.error(errmsg)
            raise IndexError(errmsg)

        return index_of_largest_width, indices_orthogonal_to_largest_width

    def get_sizes_from_pvs(self):
        """
        Yields the sizes from PVs.
        Args: None
        Yields:
            The values from x_size_pv, y_size_pv.
        """
        yield from bps.rd(self.oav.x_size_pv)
        yield from bps.rd(self.oav.y_size_pv)

    def get_scale(self, x_size, y_size):
        """
        Returns the scale of the image. The standard calculation for the image is based
        on a size of (1024, 768) so we require these scaling factors.
        Args:
            x_size: the x size of the image, in pixels
            y_size: the y size of the image, in pixels
        Returns:

        """
        return _X_SCALING_FACTOR / x_size, _Y_SCALING_FACTOR / y_size

    def find_centre(self, max_run_num=3, rotation_points=6):
        """
        Will attempt to find the OAV centre using rotation points.
        I03 gets the number of rotation points from gda.mx.loop.centring.omega.steps which defaults to 6.
        If it is unsuccessful in finding the points it will try centering a default maximum of 3 times.
        """

        # on success iteration is set equal to repeat, otherwise it is iterated
        # the algorithm will try for a maximum of `repeat` times to find the centre
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
            ) = tuple(
                self.get_spacial_data_from_pin_at_different_rotations(rotation_points)
            )

            (
                index_of_largest_width,
                indices_orthogonal_to_largest_width,
            ) = self.find_widest_point_and_orthogonal_point(
                x_positions, y_positions, widths, omega_angles
            )

            x = x_positions[index_of_largest_width]
            y = y_positions[index_of_largest_width]
            best_omega_angle = omega_angles[index_of_largest_width]

            # get the angle sufficiently orthogonal to the best omega and
            # store its mid line - which will be the magnitude in the z axis on 90 degree rotation
            index_orthogonal_to_largest_width = indices_orthogonal_to_largest_width[-1]
            best_omega_angle_orthogonal = omega_angles[
                index_orthogonal_to_largest_width
            ]
            z = mid_lines[index_orthogonal_to_largest_width][x]

            # we need to store the tips of the angles orthogonal-ish to the best angle
            orthogonal_tips_x = tip_x_positions[indices_orthogonal_to_largest_width]

            # best_omega_angle_90 could be zero, which used to cause a failure - d'oh!
            if best_omega_angle_orthogonal is None:
                LOGGER.error("Unable to find loop at 2 orthogonal angles")
                return

            # extract the max_tip_distance again as it could have changed
            self.oav_parameters.max_tip_distance = (
                self.oav_parameters._extract_dict_parameter(
                    "max_tip_distance", reload_json=True
                )
            )
            # extract the microns per pixel of the zoom level of the camera
            self.oav_parameters.load_microns_per_pixel(str(self.oav_parameters.zoom))

            # get the max tip distance in pixels
            max_tip_distance_pixels = (
                self.oav_parameters.max_tip_distance
                / self.oav_parameters.micronsPerXPixel
            )

            # get the average distance between the tips
            tip_x = np.median(orthogonal_tips_x)

            # if x exceeds the max tip distance then set it to the max tip distance
            tip_distance_pixels = x - tip_x
            if tip_distance_pixels > max_tip_distance_pixels:
                x = max_tip_distance_pixels + tip_x

            # get the scales of the image in microns
            x_size, y_size = (pv.obj.value for pv in self.get_sizes_from_pvs())
            x_scale, y_scale = self.get_scale(x_size, y_size)
            x_move, y_move = self.calculate_beam_distance_in_microns(
                int(x * x_scale), int(y * y_scale)
            )
            x_y_z_move = self.microns_to_xyz_move(x_move, y_move, best_omega_angle)

            # if we've succeeded and it's the last run then set the x_move_and y_move
            if z is not None and run_num == (max_run_num - 1):
                x_move, z_move = self.calculate_beam_distance_in_microns(
                    int(x * x_scale), int(z * y_scale)
                )
            else:
                z_move = 0  # might need to repeat process?

            x_y_z_move_2 = self.microns_to_xyz_move(
                0, z_move, best_omega_angle_orthogonal
            )
            current_motor_xyz = np.array(
                [
                    (yield from bps.rd(self.oav_goniometer.x)),
                    (yield from bps.rd(self.oav_goniometer.y)),
                    (yield from bps.rd(self.oav_goniometer.z)),
                ]
            )
            new_x, new_y, new_z = tuple(current_motor_xyz + x_y_z_move + x_y_z_move_2)
            new_y = keep_inside_bounds(new_y, -1500, 1500)
            new_z = keep_inside_bounds(new_z, -1500, 1500)

            run_num += 1

            # Now move loop to cross hair
            yield from bps.mv(
                self.oav_goniometer.x,
                new_x,
                self.oav_goniometer.y,
                new_y,
                self.oav_goniometer.z,
                new_z,
            )

        # Omega is happy to move at same time as xyz
        yield from bps.mv(self.oav_goniometer.omega, best_omega_angle)
        LOGGER.info("exiting OAVCentre")

    def calculate_beam_distance_in_microns(self, x, y):
        self._extract_beam_position()
        y_to_move = y - self.beam_centre_y
        x_to_move = self.beam_centre_x - x
        x_microns = int(x_to_move * self.oav_parameters.micronsPerXPixel)
        y_microns = int(y_to_move * self.oav_parameters.micronsPerYPixel)
        return (x_microns, y_microns)

    def microns_to_xyz_move(self, h, v, omega):
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
        x = -h
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
        z = v * sine
        y = v * cosine
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
        below_lower * -1500
        + above_upper * 1500
        + (not above_upper or below_lower) * value
    )


@bpp.run_decorator()
def oav_plan(oav: OAVCentring):
    yield from oav.pre_centring_setup_oav()


if __name__ == "__main__":
    oav = OAVCentring(
        "src/artemis/devices/unit_tests/test_OAVCentring.json",
        "src/artemis/devices/unit_tests/test_display.configuration",
        beamline="S03SIM",
    )

    RE = RunEngine()
    RE(oav_plan(oav))
