import json
from enum import IntEnum

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
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
        Sets PVs relevant to edge detection.

        Args:
            input_plugin: link to the camera stream
            min_callback_time: the value to set the minimum callback time to
            filename: filename of the python script to detect edge waveforms from camera stream.
        Returns: None
        """
        yield from bps.abs_set(self.oav.input_plugin_pv, input_plugin)

        # For an explanation of callbacks see https://nsls-ii.github.io/ophyd/area-detector.html
        yield from bps.abs_set(self.oav.enable_callbacks_pv, 1)
        yield from bps.abs_set(self.oav.min_callback_time_pv, min_callback_time)
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


@bpp.run_decorator()
def oav_plan(oav: OAVCentring):
    yield from oav.pre_centring_setup_oav()


if __name__ == "__main__":
    oav = OAVCentring(
        "src/artemis/devices/unit_tests/test_OAVCentring.json", beamline="S03SIM"
    )

    RE = RunEngine()
    RE(oav_plan(oav))
