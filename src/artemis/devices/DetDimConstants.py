class DetectorSizeConstants:

    def __init__(self, det_type_string, det_dimension, det_size_pixels, roi_dimension, roi_size_pixels):
        self.detector_type_string = det_type_string
        self.detector_dimension = det_dimension
        self.detector_size_pixels = det_size_pixels
        self.roi_dimension = roi_dimension
        self.roi_size_pixels = roi_size_pixels


class DetectorSize:

    def __init__(self, width, height):
        self.width = width
        self.height = height

    def get_width(self):
        return self.width

    def get_height(self):
        return self.height


EIGER_TYPE_EIGER2_X_4M = "EIGER2_X_4M"
EIGER2_X_4M_DIMENSION_X = 155.1
EIGER2_X_4M_DIMENSION_Y = 162.15
EIGER2_X_4M_DIMENSION = DetectorSize(EIGER2_X_4M_DIMENSION_X, EIGER2_X_4M_DIMENSION_Y)
PIXELS_X_EIGER2_X_4M = 2068
PIXELS_Y_EIGER2_X_4M = 2162
PIXELS_EIGER2_X_4M = DetectorSize(PIXELS_X_EIGER2_X_4M, PIXELS_Y_EIGER2_X_4M)
EIGER2_X_4M_SIZE = DetectorSizeConstants(EIGER_TYPE_EIGER2_X_4M, EIGER2_X_4M_DIMENSION, PIXELS_EIGER2_X_4M,
                                         EIGER2_X_4M_DIMENSION, PIXELS_EIGER2_X_4M)

EIGER_TYPE_EIGER2_X_9M = "EIGER2_X_9M"
EIGER2_X_9M_DIMENSION_X = 233.1
EIGER2_X_9M_DIMENSION_Y = 244.65
EIGER2_X_9M_DIMENSION = DetectorSize(EIGER2_X_9M_DIMENSION_X, EIGER2_X_9M_DIMENSION_Y)
PIXELS_X_EIGER2_X_9M = 3108
PIXELS_Y_EIGER2_X_9M = 3262
PIXELS_EIGER2_X_9M = DetectorSize(PIXELS_X_EIGER2_X_9M, PIXELS_Y_EIGER2_X_9M)
EIGER2_X_9M_SIZE = DetectorSizeConstants(EIGER_TYPE_EIGER2_X_9M, EIGER2_X_9M_DIMENSION, PIXELS_EIGER2_X_9M,
                                         EIGER2_X_9M_DIMENSION, PIXELS_EIGER2_X_9M)

EIGER_TYPE_EIGER2_X_16M = "EIGER2_X_16M"
EIGER2_X_16M_DIMENSION_X = 311.1
EIGER2_X_16M_DIMENSION_Y = 327.15
EIGER2_X_16M_DIMENSION = DetectorSize(EIGER2_X_16M_DIMENSION_X, EIGER2_X_16M_DIMENSION_Y)
PIXELS_X_EIGER2_X_16M = 4148
PIXELS_Y_EIGER2_X_16M = 4362
PIXELS_EIGER2_X_16M = DetectorSize(PIXELS_X_EIGER2_X_16M, PIXELS_Y_EIGER2_X_16M)
EIGER2_X_16M_SIZE = DetectorSizeConstants(EIGER_TYPE_EIGER2_X_16M, EIGER2_X_16M_DIMENSION, PIXELS_EIGER2_X_16M,
                                          EIGER2_X_4M_DIMENSION, PIXELS_EIGER2_X_4M)