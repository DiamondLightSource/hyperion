import json
import xml.etree.cElementTree as et

from artemis.devices.oav.oav_errors import (
    OAVError_BeamPositionNotFound,
    OAVError_ZoomLevelNotFound,
)


class OAVParameters:
    def __init__(
        self,
        centring_params_json,
        camera_zoom_levels_file,
        display_configuration_file,
        context="loopCentring",
    ):
        self.centring_params_json = centring_params_json
        self.camera_zoom_levels_file = camera_zoom_levels_file
        self.display_configuration_file = display_configuration_file
        self.context = context

        self.load_parameters_from_json()
        self.load_microns_per_pixel()
        self._extract_beam_position()

    def load_json(self):
        """
        Loads the json from the json file at self.centring_params_json
        """
        with open(f"{self.centring_params_json}") as f:
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
            f"Searched in {self.centring_params_json} for key {key} in context {self.context} but no value was found. No fallback value was given."
        )

    def load_microns_per_pixel(self, zoom=None):
        if not zoom:
            zoom = self.zoom

        tree = et.parse(self.camera_zoom_levels_file)
        self.micronsPerXPixel = self.micronsPerYPixel = None
        root = tree.getroot()
        levels = root.findall(".//zoomLevel")
        for node in levels:
            if float(node.find("level").text) == zoom:
                self.micronsPerXPixel = float(node.find("micronsPerXPixel").text)
                self.micronsPerYPixel = float(node.find("micronsPerYPixel").text)
        if self.micronsPerXPixel is None or self.micronsPerYPixel is None:
            raise OAVError_ZoomLevelNotFound(
                f"Could not find the micronsPer[X,Y]Pixel parameters in {self.camera_zoom_levels_file} for zoom level {zoom}."
            )

        # get the max tip distance in pixels
        self.max_tip_distance_pixels = self.max_tip_distance / self.micronsPerXPixel

    def _extract_beam_position(self):
        """

        Extracts the beam location in pixels `xCentre` `yCentre` extracted
        from the file display.configuration. The beam location is manually
        inputted by the beamline operator GDA by clicking where on screen a
        scintillator ligths up.
        """
        with open(self.display_configuration_file, "r") as f:
            file_lines = f.readlines()
            for i in range(len(file_lines)):
                if file_lines[i].startswith("zoomLevel = " + str(self.zoom)):
                    crosshair_x_line = file_lines[i + 1]
                    crosshair_y_line = file_lines[i + 2]
                    break

            if crosshair_x_line is None or crosshair_y_line is None:
                raise OAVError_BeamPositionNotFound(
                    f"Could not extract beam position at zoom level {self.zoom}"
                )

            self.beam_centre_x = int(crosshair_x_line.split(" = ")[1])
            self.beam_centre_y = int(crosshair_y_line.split(" = ")[1])

    def calculate_beam_distance(self, horizontal_pixels: int, vertical_pixels: int):
        """
        Calculates the distance between the beam centre and the given (horizontal, vertical),
        """

        return (
            self.beam_centre_x - horizontal_pixels,
            self.beam_centre_y - vertical_pixels,
        )
