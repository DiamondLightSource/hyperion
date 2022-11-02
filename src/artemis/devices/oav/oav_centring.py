from time import sleep

from artemis.devices.oav.oav_detector import OAV, Backlight, Camera, Goniometer


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
        self.oav_camera = Camera(name="oav-camera", prefix=beamline + "-EA-OAV-01:")
        self.oav_backlight = Backlight(
            name="oav-backlight", prefix=beamline + "-MO-MD2-01:"
        )
        self.oav_goniometer = Goniometer(name="oav-goniometer", prefix="-MO-GONIO-01:")
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

        # zoom is an integer value, stored as a float in a string so
        # we may need a .0 on the end? GDA does this with
        # zoomString = '%1.0dx' % float(zoom)
        # which seems suspicious
        self.oav_camera.zoom.put(f"{float(int(zoom))}x")

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

    """
    def run_calcs(points, parameter_bundle, rotateDirection=0):

        # use for tracking time of spin (FvD)
        elapsed = lambda msg, refT = time(): update('---> after %4.1fs: %s' % (round(time() - refT, 2), msg))
        elapsed('start')

        # now the business end (FvD)

        gonomega.waitWhileBusy()

        increment = 180.0 / points
        if rotateDirection == 1 or (gonomega.getUpperMotorLimit() and gonomega() + 180 > gonomega.getUpperMotorLimit()):  # MXGDA-2398
            increment = -increment

        xs, ys, sizes, gonps = (dnp.array([], dtype=dnp.int) for i in range(4))
        midarrays = []
        tip_x_y_array = []

        for i in range(points):

            if isI041():
                brightness_to_use = parameter_bundle.get_brightness()
                blbrightness.moveTo(brightness_to_use)

            (a, b) = _load_arrays(parameter_bundle)
            (x, y, size, midarray) = _midpoint_x(a, b, parameter_bundle)

            # Build arrays of edges and width, and store corresponding gonomega
            xs = dnp.append(xs, int(x))
            ys = dnp.append(ys, int(y))
            sizes = dnp.append(sizes, int(size))
            gonps = dnp.append(gonps, int(round(gonomega())))
            midarrays.append(midarray)
            tip_x_y = mxsc_plugin.get_results()
            tip_x_y_array.append(tip_x_y)

            if i < points - 1:
                gonomega(gonomega() + increment)
                elapsed('omega: %5.1f' % gonomega.position)

        return(xs, ys, sizes, gonps, midarrays, tip_x_y_array)


    def OAVCentre(self, maxRepeats=3, steps=2):
        minRuns = 1
        repeat = 0
        z = None

        while repeat < maxRepeats:
            # Do omega spin and harvest edge information
            parity = repeat % 2
            (
                x_array,
                y_array,
                size_array,
                gon_omega_array,
                mid_array_array,
                tip_x_y_array,
            ) = _run_calcs(steps, parameter_bundle, parity)

            # Do the maths...
            x_array2, y_array2, size_array2, gon_omega_array2, tip_x_array2 = (
                dnp.array([], dtype=dnp.int) for i in range(5)
            )
            non_zero_x_array = dnp.nonzero(x_array)
            if len(non_zero_x_array) > 0:
                x_median = dnp.median(x_array[non_zero_x_array[0]])
            else:
                logger.warn("Unable to find loop - all values zero")
                return

            for i in range(0, len(x_array)):
                if (
                    abs(x_array[i] - x_median) < 100 and y_array[i] > 0
                ):  # lose outliers, eg x=0, or picking up pin not loop
                    x_array2, y_array2, size_array2, gon_omega_array2 = (
                        dnp.append(x_array2, x_array[i]),
                        dnp.append(y_array2, y_array[i]),
                        dnp.append(size_array2, size_array[i]),
                        dnp.append(gon_omega_array2, gon_omega_array[i]),
                    )
                    tip_x_array2 = dnp.append(tip_x_array2, tip_x_y_array[i][0])

            if len(size_array2) > 0:
                pos_with_largest_size = size_array2.argmax()
            else:
                logger.warn("Unable to find loop - no values pass validity test")
                return

            # Find omega for face-on position: where bulge was widest
            best_gon_omega = gon_omega_array2[pos_with_largest_size]
            best_gon_omega_90 = None
            (x, y) = x_array2[pos_with_largest_size], y_array2[pos_with_largest_size]
            for i in range(
                0, len(gon_omega_array)
            ):  # deliberately not gon_omega_array2
                if 85 < abs(gon_omega_array[i] - best_gon_omega) < 95:
                    best_gon_omega_90 = gon_omega_array[i]
                    z = int(mid_array_array[i][x])

            if (
                best_gon_omega_90 == None
            ):  # best_gon_omega_90 could be zero, which used to cause a failure - d'oh!
                logger.warn("Unable to find loop at 2 orthogonal angles")
                return

            params = _get_OAVCentring_parameters()
            max_tip_distance = extract_dict_parameter(
                params, "loopCentring", "max_tip_distance", fallback_required=False
            )
            if max_tip_distance is not None:
                microns_per_pixel = BCMFinder.getOpticalCamera().getMicronsPerXPixel()
                max_tip_distance_pixels = max_tip_distance / microns_per_pixel
                tip_x = dnp.median(tip_x_array2)
                tip_distance_pixels = x - tip_x
                if tip_distance_pixels > max_tip_distance_pixels:
                    x = max_tip_distance_pixels + tip_x

            x_scale, y_scale = _getScale()

            if isI24():  # I24-288
                x_move, y_move = Utilities.pixelToMicronMove(
                    int(y * x_scale), int(x * y_scale)
                )  # OAV MXSampleDetect assumes horizontal gonio, so flip x and y here
                z_move, _ = Utilities.pixelToMicronMove(
                    int(z * x_scale), int(x * y_scale)
                )
                if best_gon_omega_90 > best_gon_omega:
                    z_move = -z_move
                x_y_z_move = [-x_move, y_move, z_move]
                gonomega.moveTo(
                    best_gon_omega
                )  # have to move to this angle first, so samxyz is correct
                new_x, new_y, new_z = sum_corresponding(
                    samplexyz.getPosition(), x_y_z_move
                )
                repeat = maxRepeats  # only run once on i24
            else:
                x_move, y_move = Utilities.pixelToMicronMove(
                    int(x * x_scale), int(y * y_scale)
                )
                x_y_z_move = Utilities.micronToXYZMove(x_move, y_move, best_gon_omega)

                if z is not None and repeat >= (minRuns - 1):
                    x_move, z_move = Utilities.pixelToMicronMove(
                        int(x * x_scale), int(z * y_scale)
                    )
                    repeat = maxRepeats
                else:
                    z_move = 0  # might need to repeat process?
                    repeat = repeat + 1

                x_y_z_move_2 = Utilities.micronToXYZMove(0, z_move, best_gon_omega_90)
                new_x, new_y, new_z = sum_corresponding(
                    samplexyz(), x_y_z_move, x_y_z_move_2
                )

                if isPhase1():
                    new_y = max(new_y, -1500)
                    new_y = min(new_y, 1500)
                    new_z = max(new_z, -1500)
                    new_z = min(new_z, 1500)

            # Now move loop to cross hair; but only wait for the move if there's another iteration coming.  FvD 2014-05-28
            samplexyz([new_x, new_y, new_z])

        gonomega.moveTo(best_gon_omega)  # is happy to move at same time as xyz
        logger.trace("exiting OAVCentre")
"""


if __name__ == "__main__":
    oav = OAVCentring(beamline="S03SIM")

    oav.setupOAV()
