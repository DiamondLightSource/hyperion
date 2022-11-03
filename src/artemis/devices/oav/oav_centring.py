import json
import os
from time import sleep

import scisoftpy as dnp

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

    def load_microns_per_pixel(self, zoom):
        dir_path = os.path.dirname(os.path.realpath(__file__))
        f = open(f"{dir_path}/microns_for_zoom_levels.json")
        json_dict = json.load(f)
        self.micronsPerXPixel = json_dict[zoom]["micronsPerXPixel"]
        self.micronsPerYPixel = json_dict[zoom]["micronsPerYPixel"]

    def load_parameters_from_file(self, context: str = "loopCentring") -> None:
        """
        A very termporary solution to help me do testing. Eventually we'll get
        this through GDA. For now OAVCentering.json is a copy of the file GDA uses
        """

        dir_path = os.path.dirname(os.path.realpath(__file__))
        f = open(f"{dir_path}/OAVCentring.json")
        self.parameters = json.load(f)

        self.exposure = self.extract_dict_parameter(context, "exposure")
        self.acquisition_period = self.extract_dict_parameter(context, "acqPeriod")
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

    def setupOAV(self, context="loopCentring"):
        """Setup OAV PVs with required values."""

        self.oav_parameters.load_parameters_from_file(context)

        self.oav.oavColourMode.put(self.oav_parameters.rgb_mode)
        self.oav.acqPeriodPV.put(self.oav_parameters.acquisition_period)
        self.oav.exposurePV.put(self.oav_parameters.exposure)
        self.oav.gainPV.put(self.oav_parameters.gain)

        # select which blur to apply to image
        self.oav.preprocess_operation_pv.put(self.oav_parameters.preprocess)

        # sets length scale for blurring
        self.oav.preprocess_ksize_pv.put(self.oav_parameters.preprocess_K_size)

        # Canny edge detect
        self.oav.canny_lower_threshold_pv.put(
            self.oav_parameters.canny_edge_lower_threshold
        )
        self.oav.canny_upper_threshold_pv.put(
            self.oav_parameters.canny_edge_upper_threshold
        )
        # "Close" morphological operation
        self.oav.close_ksize_pv.put(self.oav_parameters.close_ksize)

        # Sample detection
        self.oav.sample_detection_scan_direction_pv.put(self.oav_parameters.direction)
        self.oav.sample_detection_min_tip_height_pv.put(
            self.oav_parameters.minimum_height
        )

        # Connect MXSC output to MJPG input
        self.oav.start_mxsc(
            self.oav_parameters.input_plugin + "." + self.oav_parameters.mxsc_input,
            self.oav_parameters.min_callback_time,
            self.oav_parameters.filename,
        )

        self.oav.inputPV.put(self.oav_parameters.input_plugin + ".MXSC")

        current_zoom = self.oav_camera.zoom.get()

        # zoom is an integer value, stored as a float in a string so
        # we may need a .0 on the end? GDA does this with
        # zoomString = '%1.0dx' % float(zoom)
        # which seems suspicious
        self.oav_camera.zoom.put(f"{float(int(self.oav_parameters.zoom))}x")

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
        if current_zoom != self.oav_parameters.zoom:
            sleep(2)

    def _load_arrays(self):
        sleep(2 * self.oav_parameters.min_callback_time)
        top = dnp.array(self.oav.top_pv.get())
        bottom = dnp.array(self.oav.bottom_pv.get())
        direction = self.oav_parameters.direction
        if direction == Direction.TOP_TO_BOTTOM:  # I24-288
            y_size = self.oav.ySizePV.get()
            top = top[:y_size]
            bottom = bottom[:y_size]
        return (top, bottom)

    def _smooth(self, y):
        # GDA will always have smoothing_window be 50 for Phase1() (I03 is included)
        smoothing_window = 50
        box = dnp.ones(smoothing_window) / smoothing_window
        y_smooth = dnp.convolve(y, box, mode="same")
        return y_smooth

    def _midpoint_x(self, top, bottom, parameter_bundle):
        dif = bottom - top  # widths
        mid = (bottom + top) * 0.5  # midline
        smoothed_width = self._smooth(dif)  # smoothed widths
        first_derivative = dnp.gradient(smoothed_width)  # gradient
        reversed_deriv = first_derivative[::-1]
        reversed_grad = self._smooth(reversed_deriv)
        grad = reversed_grad[::-1]

        crossing_to_use = parameter_bundle.get_crossing()

        """
        try:
        """
        x_pos = dnp.crossings(grad, -0.01)[crossing_to_use]
        y_pos = mid[int(x_pos)]
        diff_at_x_pos = dif[int(x_pos)]
        """
        TODO: figure out what this is excepting and put it in explicitly
        except:
            x_size = len(top)  # see I24-288
            if smoothed_width[x_size - 1] > 0:
                x_pos = x_size - 1
            else:
                x_pos = 0
            y_pos = 0
            diff_at_x_pos = 0
        """
        return (x_pos, y_pos, diff_at_x_pos, mid)

    def run_calcs(self, points, parameter_bundle, rotateDirection=0):

        """
        # use for tracking time of spin (FvD)
        elapsed = lambda msg, refT=time(): update(
            "---> after %4.1fs: %s" % (round(time() - refT, 2), msg)
        )
        elapsed("start")
        """
        # now the business end (FvD)

        self.oav_goniometer.wait_for_connection()

        increment = 180.0 / points
        if rotateDirection == 1 or (
            self.oav_goniometer.omega.high_limit
            and self.oav_goniometer.omega.high_limit + 180
            > self.oav_goniometer.omega.high_limit
        ):  # MXGDA-2398
            increment = -increment

        xs, ys, sizes, gonps = (dnp.array([], dtype=dnp.int) for i in range(4))
        midarrays = []
        tip_x_y_array = []

        for i in range(points):
            (a, b) = self._load_arrays(parameter_bundle)
            (x, y, size, midarray) = self._midpoint_x(a, b, parameter_bundle)

            # Build arrays of edges and width, and store corresponding gonomega
            xs = dnp.append(xs, int(x))
            ys = dnp.append(ys, int(y))
            sizes = dnp.append(sizes, int(size))
            gonps = dnp.append(gonps, int(round(self.oav_goniometer.omega.get())))
            midarrays.append(midarray)
            tip_x_y = (self.oav.tip_x_pv.get(), self.oav.tip_y_pv.get())
            tip_x_y_array.append(tip_x_y)

            if i < points - 1:
                self.oav_goniometer.omega.put(
                    self.oav_goniometer.omega.get() + increment
                )

        return (xs, ys, sizes, gonps, midarrays, tip_x_y_array)

    def OAVCentre(self, maxRepeats=3, steps=2):
        # minRuns = 1
        repeat = 0
        # z = None

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
            ) = self.run_calcs(steps, parity)

            # Do the maths...
            x_array2, y_array2, size_array2, gon_omega_array2, tip_x_array2 = (
                dnp.array([], dtype=dnp.int) for i in range(5)
            )
            non_zero_x_array = dnp.nonzero(x_array)
            if len(non_zero_x_array) > 0:
                x_median = dnp.median(x_array[non_zero_x_array[0]])
            else:
                # logger.warn("Unable to find loop - all values zero")
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
                # logger.warn("Unable to find loop - no values pass validity test")
                return

            # Find omega for face-on position: where bulge was widest
            best_gon_omega = gon_omega_array2[pos_with_largest_size]
            best_gon_omega_90 = None
            x = x_array2[pos_with_largest_size]
            # y = y_array2[pos_with_largest_size]
            for i in range(
                0, len(gon_omega_array)
            ):  # deliberately not gon_omega_array2
                if 85 < abs(gon_omega_array[i] - best_gon_omega) < 95:
                    best_gon_omega_90 = gon_omega_array[i]
                    # z = int(mid_array_array[i][x])

            if (
                best_gon_omega_90 is None
            ):  # best_gon_omega_90 could be zero, which used to cause a failure - d'oh!
                # logger.warn("Unable to find loop at 2 orthogonal angles")
                return

            # TODO replace this to only update the max tip distance
            # Should figure out what is actually updating first

            self.oav_parameters.load_parameters_from_file()
            if self.oav_parameters.max_tip_distance is not None:
                self.oav_parameters.load_microns_per_pixel(
                    str(self.oav_parameters.zoom)
                )
                max_tip_distance_pixels = (
                    self.oav_parameters.max_tip_distance
                    / self.oav_parameters.micronsPerXPixel
                )
                tip_x = dnp.median(tip_x_array2)
                tip_distance_pixels = x - tip_x
                if tip_distance_pixels > max_tip_distance_pixels:
                    x = max_tip_distance_pixels + tip_x


"""
            x_size, y_size = self.oav.xSizePV.get(), self.oav.ySizePV.get()


            x_scale = 1024.0 / x_size
            y_scale = 768.0 / y_size


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
            new_y = max(new_y, -1500)
            new_y = min(new_y, 1500)
            new_z = max(new_z, -1500)
            new_z = min(new_z, 1500)

            # Now move loop to cross hair; but only wait for the move if there's another iteration coming.  FvD 2014-05-28
            samplexyz([new_x, new_y, new_z])

        self.oav_goniometer.omega.put(
            best_gon_omega
        )  # is happy to move at same time as xyz

    # logger.trace("exiting OAVCentre")


public double[] micronToXYZMove(double h, double v, double b, double omega) {
        // This is designed for phase 1 mx, with the hardware located to the right of the beam, and the z axis is
        // perpendicular to the beam and normal to the rotational plane of the omega axis. When the x axis is vertical
        // then the y axis is anti-parallel to the beam direction.

        // On I24, the hardware is located to the right of the beam. The x axis is along the rotation axis, and at
        // omega=0, the y axis is along the beam and the z axis is vertically down.

        // By definition, when omega = 0, the x axis will be positive in the vertical direction and a positive omega
        // movement will rotate clockwise when looking at the viewed down z-axis. This is standard in
        // crystallography.

        double z = gonioOnLeftOfImage ? h : -h;

        double angle = Math.toRadians(omega);
        double cosine = cos(angle);

        // These calculations are done as though we are looking at the back of
        // the gonio, with the beam coming from the left. They follow the
        // mathematical convention that X +ve goes right, Y +ve goes vertically
        // up. Z +ve is away from the gonio (away from you). This is NOT the
        // standard phase I convention.

        // x = b * cos - v * sin, y = b * sin + v * cos : when b is zero, only calculate v terms

        boolean anticlockwiseOmega = omegaDirection == OmegaDirection.ANTICLOCKWISE;
        // flipping the expected sign of sine(angle) here simplifies the net x,y expressions,
        // the anti-clockwise is a negative angle
        double minus_sine = anticlockwiseOmega ? sin(angle) : -sin(angle);

        double x = v * minus_sine;
        double y = v * cosine;
        if (allowBeamAxisMovement) {
            x += b * cosine;
            y -= b * minus_sine;
        }

        RealVector movement = MatrixUtils.createRealVector(new double[] {x, y, z});
        RealVector beamlineMovement = axisOrientationMatrix.operate(movement);
        return beamlineMovement.getData();
    }
"""
"""
    public double[] pixelToMicronMove(int horizDisplayClicked, int vertDisplayClicked) {
        BeamData currentBeamData = beamDataComponent.getCurrentBeamData();
        if (currentBeamData == null) {
            return new double[] {0, 0};
        }

        int vertMove = vertDisplayClicked - currentBeamData.yCentre;
        int horizMove = currentBeamData.xCentre - horizDisplayClicked;

        return pixelsToMicrons(horizMove, vertMove);
    }
"""

if __name__ == "__main__":
    oav = OAVCentring(beamline="S03SIM")

    oav.setupOAV()
