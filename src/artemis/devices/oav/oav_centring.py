from time import sleep

from artemis.devices.oav.oav_detector import OAV, Backlight, Camera


class OAVParameters:
    def __init__(self):
        self.load_parameters_from_file()

    def load_parameters_from_file(self) -> None:
        """
        A very termporary solution to help me do testing. Eventually we'll get
        this through GDA. For now OAVCentering.json is a copy of the file GDA uses
        """

        import json
        import os

        dir_path = os.path.dirname(os.path.realpath(__file__))
        f = open(f"{dir_path}/OAVCentring.json")
        self.parameters = json.load(f)

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
        self.oav_camera = Camera(name="oav-camera", prefix=beamline + "-EA-OAV-01")
        self.oav_backlight = Backlight(
            name="oav-backlight", prefix=beamline + "-MO-MD2-01"
        )
        self.oav_parameters = OAVParameters()
        self.oav.wait_for_connection()

    def setupOAV(self, context="loopCentring"):
        """Setup OAV PVs with required values."""

        rgb_mode = 2
        exposure = self.oav_parameters.extract_dict_parameter(context, "exposure")
        acquisition_period = self.oav_parameters.extract_dict_parameter(
            context, "acqPeriod"
        )
        gain = self.oav_parameters.extract_dict_parameter(context, "gain")
        canny_edge_upper_threshold = self.oav_parameters.extract_dict_parameter(
            context, "CannyEdgeUpperThreshold"
        )
        canny_edge_lower_threshold = self.oav_parameters.extract_dict_parameter(
            context, "CannyEdgeLowerThreshold", 5.0
        )
        minimum_height = self.oav_parameters.extract_dict_parameter(
            context, "minheight"
        )
        zoom = self.oav_parameters.extract_dict_parameter(context, "zoom")
        # gets blur type, e.g. 8 = gaussianBlur, 9 = medianBlur
        preprocess = self.oav_parameters.extract_dict_parameter(context, "preprocess")
        # length scale for blur preprocessing
        preprocess_K_size = self.oav_parameters.extract_dict_parameter(
            context, "preProcessKSize"
        )
        filename = self.oav_parameters.extract_dict_parameter(context, "filename")
        close_ksize = self.oav_parameters.extract_dict_parameter(
            context, "close_ksize", 11
        )

        self.oav.oavColourMode.put(rgb_mode)
        self.oav.acqPeriodPV.put(acquisition_period)
        self.oav.exposurePV.put(exposure)
        self.oav.gainPV.put(gain)

        input_plugin = self.oav_parameters.extract_dict_parameter(
            context, "oav", fallback_value="OAV"
        )
        mxsc_input = self.oav_parameters.extract_dict_parameter(
            context, "mxsc_input", fallback_value="CAM"
        )
        min_callback_time = self.oav_parameters.extract_dict_parameter(
            context, "min_callback_time", fallback_value=0.08
        )
        self.oav.start_mxsc(
            input_plugin + "." + mxsc_input, min_callback_time, filename
        )

        # Preprocess
        self.oav.preprocess_operation_pv.put(preprocess)  # which blur to apply to image
        self.oav.preprocess_ksize_pv.put(
            preprocess_K_size
        )  # sets length scale for blurring

        # Canny edge detect
        self.oav.canny_lower_threshold_pv.put(canny_edge_lower_threshold)
        self.oav.canny_upper_threshold_pv.put(canny_edge_upper_threshold)

        # "Close" morphological operation
        self.oav.close_ksize_pv.put(close_ksize)

        # Sample detection
        direction = self.oav_parameters.extract_dict_parameter(context, "direction")
        self.oav.sample_detection_scan_direction_pv.put(direction)
        self.oav.sample_detection_min_tip_height_pv.put(minimum_height)

        # Connect MXSC output to MJPG input
        self.oav.inputPV.put(input_plugin + ".MXSC")

        current_zoom = self.oav_camera.zoom.get()
        self.oav_camera.zoom.put(zoom)
        if self.oav_backlight.control.get() == "Out":
            self.oav_backlight.control.put("In")
            # TODO: Cut down on the amount of time to sleep
            sleep(1)

        """
       TODO: currently can't find the backlight brightness
         brightnessToUse = self.oav_parameters.extract_dict_parameter(
            context, "brightness"
        )

        blbrightness.moveTo(brightnessToUse)
        """

        # TODO: This seems remarkably innefficient,
        # It will sleep for 2 seconds no matter what so long as the zoom isn't correct on launch.
        if current_zoom != zoom:
            sleep(2)


if __name__ == "__main__":
    oav = OAVCentring(beamline="S03SIM")

    oav.setupOAV()
