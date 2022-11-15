import json
from enum import IntEnum

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


# Not currently in use, but will be when we add later logic
class Direction(IntEnum):
    LEFT_TO_RIGHT = 1
    RIGHT_TO_LEFT = 2
    TOP_TO_BOTTOM = 3


# Not currently in use, but will be when we add later logic
class NewDirection(IntEnum):
    RIGHT_TO_LEFT = 0
    BOTTOM_TO_TOP = 1
    LEFT_TO_RIGHT = 2
    TOP_TO_BOTTOM = 3


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

        self.exposure = self._extract_dict_parameter(self.context, "exposure")
        self.acquire_period = self._extract_dict_parameter(self.context, "acqPeriod")
        self.gain = self._extract_dict_parameter(self.context, "gain")
        self.canny_edge_upper_threshold = self._extract_dict_parameter(
            self.context, "CannyEdgeUpperThreshold"
        )
        self.canny_edge_lower_threshold = self._extract_dict_parameter(
            self.context, "CannyEdgeLowerThreshold", fallback_value=5.0
        )
        self.minimum_height = self._extract_dict_parameter(self.context, "minheight")
        self.zoom = self._extract_dict_parameter(self.context, "zoom")
        # gets blur type, e.g. 8 = gaussianBlur, 9 = medianBlur
        self.preprocess = self._extract_dict_parameter(self.context, "preprocess")
        # length scale for blur preprocessing
        self.preprocess_K_size = self._extract_dict_parameter(
            self.context, "preProcessKSize"
        )
        self.filename = self._extract_dict_parameter(self.context, "filename")
        self.close_ksize = self._extract_dict_parameter(
            self.context, "close_ksize", fallback_value=11
        )

        self.input_plugin = self._extract_dict_parameter(
            self.context, "oav", fallback_value="OAV"
        )
        self.mxsc_input = self._extract_dict_parameter(
            self.context, "mxsc_input", fallback_value="CAM"
        )
        self.min_callback_time = self._extract_dict_parameter(
            self.context, "min_callback_time", fallback_value=0.08
        )

        self.direction = self._extract_dict_parameter(self.context, "direction")

        self.max_tip_distance = self._extract_dict_parameter(
            self.context, "max_tip_distance"
        )

    def _extract_dict_parameter(
        self, context: str, key: str, fallback_value=None, reload_json=False
    ):
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
        When we extract the parameters we want to check if the given context contains a
        parameter, if it does we return it, if not we return the global value. If a parameter
        is not found at all then the passed in fallback_value is returned. If that isn't found
        then an error is raised.

        Args:
            context: the context to search for the prefered value
            key: the key of the value being extracted
            fallback_value: a value to be returned if the key is not found
            reload_json: reload the json from the file before searching for it, needed because some
                parameters can change mid operation.

        Returns: The extracted value corresponding to the key, or the fallback_value if none is found.
        """

        if reload_json:
            self.load_json()

        if context in self.parameters:
            if key in self.parameters[context]:
                return self.parameters[context][key]

        if key in self.parameters:
            return self.parameters[key]

        if fallback_value:
            return fallback_value

        # No fallback_value was given and the key wasn't found
        raise KeyError(
            f"Searched in {self.file} for key {key} in context {context} but no value was found. No fallback value was given."
        )


class OAVCentring:
    def __init__(self, parameters_file, beamline="BL03I"):
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

    def get_formatted_edge_waveforms(self):
        """
        Get the waveforms from the PVs as numpy arrays.
        """
        top = np.array((yield from bps.rd(self.oav.top_pv)))
        bottom = np.array((yield from bps.rd(self.oav.bottom_pv)))
        return (top, bottom)

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

    def calculate_centres_at_different_rotations(self, points: int):
        """
        Calculate relevant spacial points at each rotation and save them in lists.

        Args:
            points: the number of rotation points
        Returns:
            Relevant lists for each rotation:
                x_y_positions: tuples of the form (x,y) for found centres
                widths: the widths between the top and bottom waveforms at the centre point
                omega_angles: the angle of the goniometer at which the measurement was taken
                mid_lines: the waveform going between the top and bottom waveforms
                tip_x_y_positions: tuples of the form (x,y) for the measured x and y tips
        """
        self.oav_goniometer.wait_for_connection()

        # number of degrees to rotate to
        increment = 180.0 / points

        # if the rotation threshhold would be exceeded flip the rotation direction
        if (yield from bps.rd(self.oav_goniometer.omega)) + 180 > (
            yield from self.oav_goniometer.omega.high_limit
        ):
            increment = -increment

        # Arrays to hold positiona data of the pin at each rotation
        x_y_positions = []
        widths = []
        omega_angles = []
        mid_lines = []
        tip_x_y_positions = []

        for i in range(points):
            current_omega = yield from self.oav_goniometer.omega
            (a, b) = self.get_formatted_edge_waveforms()
            (x, y, width, mid_line) = self.find_midpoint(a, b)

            # Build arrays of edges and width, and store corresponding gonomega
            x_y_positions.append((x, y))
            widths.append(width)
            omega_angles.append(current_omega)
            mid_lines.append(mid_line)
            tip_x = yield from bps.rd(self.oav.tip_x_pv)
            tip_y = yield from bps.rd(self.oav.tip_x_pv)
            tip_x_y_positions.append((tip_x, tip_y))

            # rotate the pin to take next measurement, unless it's the last measurement
            if i < points - 1:
                yield from bps.mv(self.oav_goniometer.omega, current_omega + increment)

        return (
            x_y_positions,
            widths,
            omega_angles,
            mid_lines,
            tip_x_y_positions,
        )


@bpp.run_decorator()
def oav_plan(oav: OAVCentring):
    yield from oav.pre_centring_setup_oav()


if __name__ == "__main__":
    oav = OAVCentring(
        "src/artemis/devices/unit_tests/test_OAVCentring.json", beamline="S03SIM"
    )

    RE = RunEngine()
    RE(oav_plan(oav))
