from numpy import loadtxt, interp
from enum import Enum

from src.artemis.devices.det_dim_constants import DetectorSizeConstants


class DetectorDistanceToBeamXYConverter:
	lookup_file: str
	lookup_table_values: list

	class Axis(Enum):
		Y_AXIS = 1
		X_AXIS = 2

	def __init__(self, lookup_file: str):
		self.lookup_file = lookup_file
		self.lookup_table_values = self.parse_table()

	def get_beam_xy_from_det_dist_mm(self, det_dist_mm: float, beam_axis: Axis) -> float:
		beam_axis_values = self.lookup_table_values[beam_axis.value]
		det_dist_array = self.lookup_table_values[0]
		return interp(det_dist_mm, det_dist_array, beam_axis_values)

	def get_beam_axis_pixels(self, det_distance: float, image_size_pixels: int, det_dim: float, beam_axis: Axis) -> float:
		beam_mm = self.get_beam_xy_from_det_dist_mm(det_distance, beam_axis)
		return beam_mm * image_size_pixels / det_dim

	def get_beam_y_pixels(self, det_distance: float, image_size_pixels: int, det_dim: float) -> float:
		return self.get_beam_axis_pixels(det_distance, image_size_pixels, det_dim, DetectorDistanceToBeamXYConverter.Axis.Y_AXIS)

	def get_beam_x_pixels(self, det_distance: float, image_size_pixels: int, det_dim: float) -> float:
		return self.get_beam_axis_pixels(det_distance, image_size_pixels, det_dim, DetectorDistanceToBeamXYConverter.Axis.X_AXIS)

	def get_beam_position_mm(self, detector_distance, detector_dimensions: DetectorSizeConstants, use_roi: bool):
		x_beam_mm = self.get_beam_xy_from_det_dist_mm(detector_distance, DetectorDistanceToBeamXYConverter.Axis.X_AXIS)
		y_beam_mm = self.get_beam_xy_from_det_dist_mm(detector_distance, DetectorDistanceToBeamXYConverter.Axis.Y_AXIS)

		full_size_mm = self.detector_dimensions.det_dimension
		roi_size_mm = self.detector_dimensions.roi_dimension if use_roi else full_size_mm

		offset_x = (full_size_mm.width - roi_size_mm.width) / 2.
		offset_y = (full_size_mm.height - roi_size_mm.height) / 2.

		return x_beam_mm - offset_x, y_beam_mm - offset_y

	def reload_lookup_table(self):
		self.lookup_table_values = self.parse_table()

	def parse_table(self) -> list:
		rows = loadtxt(self.lookup_file, delimiter=" ", comments=["#", "Units"])
		columns = list(zip(*rows))

		return columns
