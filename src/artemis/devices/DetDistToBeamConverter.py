DET_DIST_BEAMXY_LOOKUP_FILE = 'DetDistToBeamXYConverter.txt'

def parse_table(file):
	with open(file) as f:
		lines = f.readlines()
		rows = []

		for line in lines:
			if line.startswith('#') or line.startswith('\n') or line.startswith('Units'):
				continue

			line = line.strip()
			line_array = line.split(' ')
			line_array = list(map(float, line_array))
			rows.append(line_array)

		columns = list(zip(*rows))

	return columns

def get_beam_x_from_det_dist_mm(det_dist_mm):
	columns = parse_table(DET_DIST_BEAMXY_LOOKUP_FILE)
	det_dist_array = columns[0]
	beam_x_array = columns[2]

	beam_x = beam_x_array[0] + (det_dist_mm - det_dist_array[0])*(beam_x_array[1] - beam_x_array[0])/(det_dist_array[1] - det_dist_array[0])

	return beam_x

def get_beam_y_from_det_dist_mm(det_dist_mm):
        columns	= parse_table(DET_DIST_BEAMXY_LOOKUP_FILE)
        det_dist_array = columns[0]
        beam_y_array = columns[1]

        beam_y = beam_y_array[0] + (det_dist_mm - det_dist_array[0])*(beam_y_array[1] - beam_y_array[0])/(det_dist_array[1] - det_dist_array[0])

        return beam_y

def get_beam_x_pixels(det_distance, image_size_pixels, det_dim):
	beam_x_mm = get_beam_x_from_det_dist_mm(det_distance)
	return beam_x_mm * image_size_pixels / det_distance

def get_beam_y_pixels(det_distance, image_size_pixels, det_dim):
        beam_y_mm = get_beam_y_from_det_dist_mm(det_distance)
        return beam_y_mm * image_size_pixels / det_distance

