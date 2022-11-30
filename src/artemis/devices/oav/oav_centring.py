import json

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import numpy as np
from bluesky import RunEngine

from artemis.devices.backlight import Backlight
from artemis.devices.I03Smargon import I03Smargon
from artemis.devices.oav.oav_detector import OAV, ColorMode, EdgeOutputArrayImageType


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


class OAVCentring:
    def __init__(
        self,
        oav: OAV,
        smargon: I03Smargon,
        backlight: Backlight,
        parameters_file,
        display_configuration_path,
    ):
        self.oav = oav
        self.smargon = smargon
        self.backlight = backlight
        self.oav_parameters = OAVParameters(parameters_file)
        self.display_configuration_path = display_configuration_path
        self.oav.wait_for_connection()

    def pre_centring_setup_oav(self):
        """Setup OAV PVs with required values."""

        self.oav_parameters.load_parameters_from_json()

        yield from bps.abs_set(self.oav.cam.color_mode, ColorMode.RGB1)
        yield from bps.abs_set(
            self.oav.cam.acquire_period, self.oav_parameters.acquire_period
        )
        yield from bps.abs_set(self.oav.cam.acquire_time, self.oav_parameters.exposure)
        yield from bps.abs_set(self.oav.cam.gain, self.oav_parameters.gain)

        # select which blur to apply to image
        yield from bps.abs_set(
            self.oav.mxsc.preprocess_operation, self.oav_parameters.preprocess
        )

        # sets length scale for blurring
        yield from bps.abs_set(
            self.oav.mxsc.preprocess_ksize, self.oav_parameters.preprocess_K_size
        )

        # Canny edge detect
        yield from bps.abs_set(
            self.oav.mxsc.canny_lower_threshold,
            self.oav_parameters.canny_edge_lower_threshold,
        )
        yield from bps.abs_set(
            self.oav.mxsc.canny_upper_threshold,
            self.oav_parameters.canny_edge_upper_threshold,
        )
        # "Close" morphological operation
        yield from bps.abs_set(
            self.oav.mxsc.close_ksize, self.oav_parameters.close_ksize
        )

        # Sample detection
        yield from bps.abs_set(
            self.oav.mxsc.sample_detection_scan_direction, self.oav_parameters.direction
        )
        yield from bps.abs_set(
            self.oav.mxsc.sample_detection_min_tip_height,
            self.oav_parameters.minimum_height,
        )

        # Connect MXSC output to MJPG input
        yield from self.start_mxsc(
            self.oav_parameters.input_plugin + "." + self.oav_parameters.mxsc_input,
            self.oav_parameters.min_callback_time,
            self.oav_parameters.filename,
        )

        yield from bps.abs_set(
            self.oav.snapshot.input_pv, self.oav_parameters.input_plugin + ".MXSC"
        )

        yield from bps.abs_set(
            self.oav.zoom_controller.zoom,
            f"{float(self.oav_parameters.zoom)}x",
            wait=True,
        )

        if (yield from bps.rd(self.backlight.pos)) == 0:
            yield from bps.abs_set(self.backlight.pos, 1, wait=True)

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
        yield from bps.abs_set(self.oav.mxsc.input_plugin_pv, input_plugin)

        # Turns the area detector plugin on
        yield from bps.abs_set(self.oav.mxsc.enable_callbacks_pv, 1)

        # Set the minimum time between updates of the plugin
        yield from bps.abs_set(self.oav.mxsc.min_callback_time_pv, min_callback_time)

        # Stop the plugin from blocking the IOC and hogging all the CPU
        yield from bps.abs_set(self.oav.mxsc.blocking_callbacks_pv, 0)

        # Set the python file to use for calculating the edge waveforms
        yield from bps.abs_set(self.oav.mxsc.py_filename, filename, wait=True)
        yield from bps.abs_set(self.oav.mxsc.read_file, 1)

        # Image annotations
        yield from bps.abs_set(self.oav.mxsc.draw_tip, True)
        yield from bps.abs_set(self.oav.mxsc.draw_edges, True)

        # Use the original image type for the edge output array
        yield from bps.abs_set(
            self.oav.mxsc.output_array, EdgeOutputArrayImageType.ORIGINAL
        )

    def get_formatted_edge_waveforms(self):
        """
        Get the waveforms from the PVs as numpy arrays.
        """
        top = np.array((yield from bps.rd(self.oav.mxsc.top)))
        bottom = np.array((yield from bps.rd(self.oav.mxsc.bottom)))
        return (top, bottom)


@bpp.run_decorator()
def oav_plan(oav_centring: OAVCentring):
    yield from oav_centring.pre_centring_setup_oav()


if __name__ == "__main__":
    beamline = "S03SIM"
    oav = OAV(name="oav", prefix=beamline)
    smargon = I03Smargon(prefix="-MO-SGON-01:")
    backlight = Backlight(prefix="-EA-BL-01:")
    oav_centring = OAVCentring(
        oav,
        smargon,
        backlight,
        "src/artemis/devices/unit_tests/test_OAVCentring.json",
        "src/artemis/devices/unit_tests/test_display.configuration",
    )

    RE = RunEngine()
    RE(oav_plan(oav_centring))
