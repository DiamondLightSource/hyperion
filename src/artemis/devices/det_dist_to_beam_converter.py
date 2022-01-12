from numpy import loadtxt, interp

DET_DIST_BEAM_XY_LOOKUP_FILE = 'det_dist_to_beam_XY_converter.txt'


def parse_table(file):
	rows = loadtxt(file, delimiter=" ", comments=["#", "Units"])
	columns = list(zip(*rows))

	return columns


PARSED_TABLE_VALUES = parse_table(DET_DIST_BEAM_XY_LOOKUP_FILE)


def get_beam_xy_from_det_dist_mm(det_dist_mm, beam_axis_values):
	det_dist_array = PARSED_TABLE_VALUES[0]
	return interp(det_dist_mm, det_dist_array, beam_axis_values)


def get_beam_axis_pixels(det_distance, image_size_pixels, det_dim, beam_axis_values):
	beam_mm = get_beam_xy_from_det_dist_mm(det_distance, beam_axis_values)
	return beam_mm * image_size_pixels / det_dim


def get_beam_x_pixels(det_distance, image_size_pixels, det_dim):
	beam_x_values = PARSED_TABLE_VALUES[2]
	return get_beam_axis_pixels(det_distance, image_size_pixels, det_dim, beam_x_values)


def get_beam_y_pixels(det_distance, image_size_pixels, det_dim):
	beam_y_values = PARSED_TABLE_VALUES[1]
	return get_beam_axis_pixels(det_distance, image_size_pixels, det_dim, beam_y_values)


def reload_lookup_table():
	global PARSED_TABLE_VALUES
	PARSED_TABLE_VALUES = parse_table(DET_DIST_BEAM_XY_LOOKUP_FILE)
