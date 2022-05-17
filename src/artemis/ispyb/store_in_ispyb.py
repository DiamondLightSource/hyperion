import datetime
import re

from sqlalchemy.connectors import Connector
from src.artemis.ispyb.ispyb_dataclass import Orientation
from src.artemis.parameters import FullParameters

import ispyb

I03_EIGER_DETECTOR = 78
EIGER_FILE_SUFFIX = "h5"


class StoreInIspyb:

    VISIT_PATH_REGEX = r".+/([a-zA-Z]{2}\d{4,5}-\d{1,3})/"

    def __init__(self, ispyb_config):
        self.ISPYB_CONFIG_FILE = ispyb_config
        self.full_params = None
        self.ispyb_params = None
        self.detector_params = None
        self.run_number = None
        self.omega_start = None

        self.conn: Connector = None
        self.mx_acquisition = None
        self.core = None

    def store_grid_scan(self, full_params: FullParameters):

        self.full_params = full_params
        self.ispyb_params = full_params.ispyb_params
        self.detector_params = full_params.detector_params
        self.run_number = self.ispyb_params.run_number
        self.omega_start = self.detector_params.omega_start

        with ispyb.open(self.ISPYB_CONFIG_FILE) as self.conn:
            self.mx_acquisition = self.conn.mx_acquisition
            self.core = self.conn.core

            return self._store_scan_data()

    def _store_scan_data(self):
        raise NotImplementedError(
            "_store_scan_data() must be implemented by a subclass"
        )

    def update_grid_scan_with_end_time_and_status(
        self, end_time: str, run_status: str, dc_id: int
    ) -> int:
        with ispyb.open(self.ISPYB_CONFIG_FILE) as self.conn:
            self.mx_acquisition = self.conn.mx_acquisition

            params = self.mx_acquisition.get_data_collection_params()
            params["id"] = dc_id
            params["endtime"] = end_time
            params["run_status"] = run_status

            return self.mx_acquisition.upsert_data_collection(list(params.values()))

    def _store_grid_info_table(self, ispyb_data_collection_id: int) -> int:
        params = self.mx_acquisition.get_dc_grid_params()

        params["parentid"] = ispyb_data_collection_id
        params["dxInMm"] = self.full_params.grid_scan_params.x_step_size
        params["dyInMm"] = self.full_params.grid_scan_params.y_step_size
        params["stepsX"] = self.full_params.grid_scan_params.x_steps
        params["stepsY"] = self.full_params.grid_scan_params.y_steps
        params["pixelsPerMicronX"] = self.ispyb_params.pixels_per_micron_x
        params["pixelsPerMicronY"] = self.ispyb_params.pixels_per_micron_y
        upper_left = self.ispyb_params.upper_left
        params["snapshotOffsetXPixel"], params["snapshotOffsetYPixel"] = upper_left
        params["orientation"] = Orientation.HORIZONTAL.value
        params["snaked"] = True

        return self.mx_acquisition.upsert_dc_grid(list(params.values()))

    def _store_data_collection_table(self, data_collection_group_id: int) -> int:
        session_id = self.core.retrieve_visit_id(self.get_visit_string())

        params = self.mx_acquisition.get_data_collection_params()
        params["visitid"] = session_id
        params["parentid"] = data_collection_group_id
        params["sampleid"] = self.ispyb_params.sample_id
        params["detectorid"] = I03_EIGER_DETECTOR
        params["axis_start"] = self.omega_start
        params["axis_end"] = self.omega_start
        params["axis_range"] = 0
        params["focal_spot_size_at_samplex"] = self.ispyb_params.focal_spot_size_x
        params["focal_spot_size_at_sampley"] = self.ispyb_params.focal_spot_size_y
        params["slitgap_vertical"] = self.ispyb_params.slit_gap_size_y
        params["slitgap_horizontal"] = self.ispyb_params.slit_gap_size_x
        params["beamsize_at_samplex"] = self.ispyb_params.beam_size_x
        params["beamsize_at_sampley"] = self.ispyb_params.beam_size_y
        params["transmission"] = self.ispyb_params.transmission
        params["comments"] = "Artemis: " + self.ispyb_params.comment
        params["datacollection_number"] = self.run_number
        params["detector_distance"] = self.detector_params.detector_distance
        params["exp_time"] = self.detector_params.exposure_time
        params["imgdir"] = self.detector_params.directory
        params["imgprefix"] = self.detector_params.prefix
        params["imgsuffix"] = EIGER_FILE_SUFFIX
        params["n_images"] = self.detector_params.num_images

        # Both overlap and n_passes included for backwards compatibility, planned to be removed later
        params["n_passes"] = 1
        params["overlap"] = 0

        params["flux"] = self.ispyb_params.flux
        params["omegastart"] = self.omega_start
        params["start_image_number"] = 1
        params["resolution"] = self.ispyb_params.resolution
        params["wavelength"] = self.ispyb_params.wavelength
        beam_position = self.detector_params.get_beam_position_mm(
            self.detector_params.detector_distance
        )
        params["xbeam"], params["ybeam"] = beam_position
        params["xtal_snapshot1"], params["xtal_snapshot2"], params["xtal_snapshot3"] = [
            self.ispyb_params.xtal_snapshots
        ] * 3
        params["synchrotron_mode"] = self.ispyb_params.synchrotron_mode
        params["undulator_gap1"] = self.ispyb_params.undulator_gap
        params["starttime"] = self.get_current_time_string()

        # temporary file template until nxs filewriting is integrated and we can use that file name
        params[
            "file_template"
        ] = f"{self.detector_params.prefix}_{self.run_number}_master.h5"

        return self.mx_acquisition.upsert_data_collection(list(params.values()))

    def _store_position_table(self, dc_id: int) -> int:
        params = self.mx_acquisition.get_dc_position_params()

        params["id"] = dc_id
        (
            params["pos_x"],
            params["pos_y"],
            params["pos_z"],
        ) = self.ispyb_params.position

        return self.mx_acquisition.update_dc_position(list(params.values()))

    def _store_data_collection_group_table(self) -> int:
        session_id = self.core.retrieve_visit_id(self.get_visit_string())

        params = self.mx_acquisition.get_data_collection_group_params()
        params["parentid"] = session_id
        params["experimenttype"] = "mesh"
        params["sampleid"] = self.ispyb_params.sample_id
        params["sample_barcode"] = self.ispyb_params.sample_barcode

        return self.mx_acquisition.upsert_data_collection_group(list(params.values()))

    def get_current_time_string(self):
        now = datetime.datetime.now()
        return now.strftime("%Y-%m-%d %H:%M:%S")

    def get_visit_string(self):
        visit_path_match = self.get_visit_string_from_path(self.ispyb_params.visit_path)
        if visit_path_match:
            return visit_path_match
        else:
            return self.get_visit_string_from_path(self.detector_params.directory)

    def get_visit_string_from_path(self, path):
        match = re.search(self.VISIT_PATH_REGEX, path) if path else None
        return match.group(1) if match else None
