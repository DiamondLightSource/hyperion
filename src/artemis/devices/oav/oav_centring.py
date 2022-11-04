import json
import os

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
from bluesky import RunEngine

from artemis.devices.oav.oav_detector import OAV, Backlight, Camera, Goniometer


class Direction:
    LEFT_TO_RIGHT = 1
    RIGHT_TO_LEFT = 2
    TOP_TO_BOTTOM = 3


class NewDirection:
    RIGHT_TO_LEFT = 0
    BOTTOM_TO_TOP = 1
    LEFT_TO_RIGHT = 2
    TOP_TO_BOTTOM = 3


class OAVParameters:
    def __init__(self):
        self.rgb_mode = 2

    def load_parameters_from_file(
        self,
        context="loopCentring",
        path=os.path.dirname(os.path.realpath(__file__)),
    ) -> None:
        """
        A very termporary solution to help me do testing. Eventually we'll get
        this through GDA. For now OAVCentering.json is a copy of the file GDA uses
        """

        with open(f"{path}/OAVCentring.json") as f:
            self.parameters = json.load(f)

        self.exposure = self.extract_dict_parameter(context, "exposure")
        self.acquire_period = self.extract_dict_parameter(context, "acqPeriod")
        self.gain = self.extract_dict_parameter(context, "gain")
        self.canny_edge_upper_threshold = self.extract_dict_parameter(
            context, "CannyEdgeUpperThreshold"
        )
        self.canny_edge_lower_threshold = self.extract_dict_parameter(
            context, "CannyEdgeLowerThreshold", 5.0
        )
        self.minimum_height = self.extract_dict_parameter(context, "minheight")
        self.zoom = self.extract_dict_parameter(context, "zoom")
        # gets blur type, e.g. 8 = gaussianBlur, 9 = medianBlur
        self.preprocess = self.extract_dict_parameter(context, "preprocess")
        # length scale for blur preprocessing
        self.preprocess_K_size = self.extract_dict_parameter(context, "preProcessKSize")
        self.filename = self.extract_dict_parameter(context, "filename")
        self.close_ksize = self.extract_dict_parameter(context, "close_ksize", 11)

        self.input_plugin = self.extract_dict_parameter(
            context, "oav", fallback_value="OAV"
        )
        self.mxsc_input = self.extract_dict_parameter(
            context, "mxsc_input", fallback_value="CAM"
        )
        self.min_callback_time = self.extract_dict_parameter(
            context, "min_callback_time", fallback_value=0.08
        )

        self.direction = self.extract_dict_parameter(context, "direction")

        self.max_tip_distance = self.extract_dict_parameter(context, "max_tip_distance")

    def extract_dict_parameter(self, context: str, key: str, fallback_value=None):
        if context in self.parameters:
            if key in self.parameters[context]:
                return self.parameters[context][key]
        if key in self.parameters:
            return self.parameters[key]
        return fallback_value


class OAVCentring:
    def __init__(self, beamline="BL03I"):
        self.oav = OAV(name="oav", prefix=beamline + "-DI-OAV-01:")
        self.oav_camera = Camera(name="oav-camera", prefix=beamline + "-EA-OAV-01:")
        self.oav_backlight = Backlight(
            name="oav-backlight", prefix=beamline + "-MO-MD2-01:"
        )
        self.oav_goniometer = Goniometer(name="oav-goniometer", prefix="-MO-SGON-01:")
        self.oav_parameters = OAVParameters()
        self.oav.wait_for_connection()

    def pre_centring_setup_oav(self, context="loopCentring"):
        """Setup OAV PVs with required values."""

        self.oav_parameters.load_parameters_from_file(context)

        yield from bps.abs_set(self.oav.colour_mode_pv, self.oav_parameters.rgb_mode)
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

        if (yield from bps.rd(self.oav_backlight.control)) == "Out":
            yield from bps.abs_set(self.oav_backlight.control, "In", wait=True)

        """
       TODO: currently can't find the backlight brightness
        this will need to be set up after issue
        https://github.com/DiamondLightSource/python-artemis/issues/317
        is solved
         brightnessToUse = self.oav_parameters.extract_dict_parameter(
            context, "brightness"
        )

        blbrightness.moveTo(brightnessToUse)
        """

    def start_mxsc(self, input_plugin, min_callback_time, filename=None):
        yield from bps.abs_set(self.oav.input_plugin_pv, input_plugin)
        yield from bps.abs_set(self.oav.enable_callbacks_pv, 1)
        yield from bps.abs_set(self.oav.min_callback_time_pv, min_callback_time)
        yield from bps.abs_set(self.oav.blocking_callbacks_pv, 0)

        # I03-323
        if filename is not None:
            yield from bps.abs_set(self.oav.py_filename_pv, filename, wait=True)
            yield from bps.abs_set(self.oav.read_file_pv, 1)

        # Image annotations
        yield from bps.abs_set(self.oav.draw_tip_pv, True)
        yield from bps.abs_set(self.oav.draw_edges_pv, True)

        # Image to send downstream
        OUTPUT_ORIGINAL = 0
        yield from bps.abs_set(self.oav.output_array_pv, OUTPUT_ORIGINAL)


@bpp.run_decorator()
def oav_plan(oav: OAVCentring):
    yield from oav.pre_centring_setup_oav()


if __name__ == "__main__":
    oav = OAVCentring(beamline="S03SIM")

    RE = RunEngine()
    RE(oav_plan(oav))
