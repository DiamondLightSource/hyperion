import os

from dataclasses import dataclass, field
from typing import Tuple
from dataclasses_json import dataclass_json, config

from src.artemis.devices.det_dim_constants import DetectorSizeConstants, constants_from_type, EIGER2_X_16M_SIZE
from src.artemis.devices.det_dist_to_beam_converter import DetectorDistanceToBeamXYConverter


@dataclass_json
@dataclass
class DetectorParams:
    current_energy: float
    exposure_time: float
    acquisition_id: int
    directory: str
    prefix: str
    detector_distance: float
    omega_start: float
    omega_increment: float
    num_images: int

    use_roi_mode: bool

    detector_size_constants: DetectorSizeConstants = field(
        default=EIGER2_X_16M_SIZE,
        metadata=config(
            encoder=lambda detector: detector.det_type_string,
            decoder=lambda det_type: constants_from_type(det_type),
        ),
    )

    beam_xy_converter: DetectorDistanceToBeamXYConverter = field(
        default=DetectorDistanceToBeamXYConverter(os.path.join(
                    os.path.dirname(__file__),
                    "det_dist_to_beam_XY_converter.txt",
                )),
        metadata=config(
            encoder=lambda converter: converter.lookup_file,
            decoder=lambda path_name: DetectorDistanceToBeamXYConverter(path_name)
        )
    )

    def get_beam_position_mm(self, detector_distance: float) -> Tuple[float, float]:
        x_beam_mm = self.get_beam_xy_from_det_dist_mm(detector_distance, DetectorDistanceToBeamXYConverter.Axis.X_AXIS)
        y_beam_mm = self.get_beam_xy_from_det_dist_mm(detector_distance, DetectorDistanceToBeamXYConverter.Axis.Y_AXIS)

        full_size_mm = self.detector_size_constants.det_dimension
        roi_size_mm = self.detector_size_constants.roi_dimension if self.use_roi_mode else full_size_mm

        offset_x = (full_size_mm.width - roi_size_mm.width) / 2.
        offset_y = (full_size_mm.height - roi_size_mm.height) / 2.

        return x_beam_mm - offset_x, y_beam_mm - offset_y

    def get_beam_position_pixels(self, detector_distance: float) -> Tuple[float, float]:
        full_size_pixels = self.detector_size_constants.det_size_pixels
        roi_size_pixels = self.detector_size_constants.roi_size_pixels if self.use_roi_mode else full_size_pixels
        
        x_beam_pixels = self.beam_xy_converter.get_beam_x_pixels(
            detector_distance, full_size_pixels.width, self.detector_size_constants.det_dimension.width
        )
        y_beam_pixels = self.beam_xy_converter.get_beam_y_pixels(
            detector_distance, full_size_pixels.height, self.detector_size_constants.det_dimension.height
        )

        offset_x = (full_size_pixels.width - roi_size_pixels.width) / 2.
        offset_y = (full_size_pixels.height - roi_size_pixels.height) / 2.

        return x_beam_pixels - offset_x, y_beam_pixels - offset_y