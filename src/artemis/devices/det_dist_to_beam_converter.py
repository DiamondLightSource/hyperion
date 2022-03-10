from numpy import loadtxt, interp
from enum import Enum


class Axis(Enum):
		Y_AXIS = 1
		X_AXIS = 2


class DetectorDistanceToBeamXYConverter:
	lookup_file: str
	lookup_table_values: list

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
		return self.get_beam_axis_pixels(det_distance, image_size_pixels, det_dim, Axis.Y_AXIS)

	def get_beam_x_pixels(self, det_distance: float, image_size_pixels: int, det_dim: float) -> float:
		return self.get_beam_axis_pixels(det_distance, image_size_pixels, det_dim, Axis.X_AXIS)

	def reload_lookup_table(self):
		self.lookup_table_values = self.parse_table()

	def parse_table(self) -> list:
		rows = loadtxt(self.lookup_file, delimiter=" ", comments=["#", "Units"])
		columns = list(zip(*rows))

		return columns
