import ispyb
from sqlalchemy.connectors import Connector

from src.artemis.ispyb.ispyb_dataclasses import GridInfo, DataCollection, DataCollectionGroup, Position


class StoreInIspyb:

    ISPYB_CONFIG_FILE = "/dls_sw/dasc/mariadb/credentials/ispyb-dev.cfg"
    conn: Connector

    def store_grid_scan(self, grid_info: GridInfo, data_collection: DataCollection, position: Position,
                        data_collection_group: DataCollectionGroup):

        with ispyb.open(self.ISPYB_CONFIG_FILE) as self.conn:
            data_collection.data_collection_group_id = self.store_data_collection_group_table(data_collection_group)
            data_collection.position_id = self.store_position_table(position)

            data_collection_id = self.store_data_collection_table(data_collection)

            grid_info.ispyb_data_collection_id = data_collection_id

            grid_id = self.store_grid_info_table(grid_info)

            return grid_id, data_collection_id


    def update_grid_scan_with_end_time_and_status(self, end_time: str, run_status: str, dc_id: int) -> int:
        with ispyb.open(self.ISPYB_CONFIG_FILE) as self.conn:
            mx_acquisition = self.conn.mx_acquisition

            params = mx_acquisition.get_data_collection_params()
            params["id"] = dc_id
            params["endtime"] = end_time
            params["run_status"] = run_status

            return mx_acquisition.upsert_data_collection(list(params.values()))

    def store_grid_info_table(self, grid_info: GridInfo) -> int:
        mx_acquisition = self.conn.mx_acquisition

        params = mx_acquisition.get_dc_grid_params()

        params["parentid"] = grid_info.ispyb_data_collection_id
        params["dxInMm"] = grid_info.dx_mm
        params["dyInMm"] = grid_info.dy_mm
        params["stepsX"] = grid_info.steps_x
        params["stepsY"] = grid_info.steps_y
        params["pixelsPerMicronX"] = grid_info.pixels_per_micron_x
        params["pixelsPerMicronY"] = grid_info.pixels_per_micron_y
        params["snapshotOffsetXPixel"] = grid_info.snapshot_offset_pixel_x
        params["snapshotOffsetYPixel"] = grid_info.snapshot_offset_pixel_y
        params["orientation"] = grid_info.orientation
        params["snaked"] = grid_info.snaked

        return mx_acquisition.upsert_dc_grid(list(params.values()))


    def store_data_collection_table(self, data_collection: DataCollection) -> int:
        core = self.conn.core
        mx_acquisition = self.conn.mx_acquisition

        sessionid = core.retrieve_visit_id(data_collection.visit)

        params = mx_acquisition.get_data_collection_params()
        params["visitid"] = sessionid
        params["parentid"] = data_collection.data_collection_group_id
        params["positonid"] = data_collection.position_id
        params["sampleid"] = data_collection.sample_id
        params["detectorid"] = data_collection.detector_id
        params["axis_start"] = data_collection.axis_start
        params["axis_end"] = data_collection.axis_end
        params["axis_range"] = data_collection.axis_range
        params["focal_spot_size_at_samplex"] = data_collection.focal_spot_size_at_sample_x
        params["focal_spot_size_at_sampley"] = data_collection.focal_spot_size_at_sample_y
        params["slitgap_vertical"] = data_collection.slitgap_vertical
        params["slitgap_horizontal"] = data_collection.slitgap_horizontal
        params["beamsize_at_samplex"] = data_collection.beamsize_at_sample_x
        params["beamsize_at_sampley"] = data_collection.beamsize_at_sample_y
        params["transmission"] = data_collection.transmission
        params["comments"] = data_collection.comments
        params["datacollection_number"] = data_collection.data_collection_number
        params["detector_distance"] = data_collection.detector_distance
        params["exp_time"] = data_collection.exposure_time
        params["imgdir"] = data_collection.img_dir
        params["imgprefix"] = data_collection.img_prefix
        params["imgsuffix"] = data_collection.img_suffix
        params["n_images"] = data_collection.number_of_images
        params["n_passes"] = data_collection.number_of_passes
        params["overlap"] = data_collection.overlap
        params["flux"] = data_collection.flux
        params["omegastart"] = data_collection.omega_start
        params["start_image_number"] = data_collection.start_image_number
        params["resolution"] = data_collection.resolution
        params["wavelength"] = data_collection.wavelength
        params["xbeam"] = data_collection.x_beam
        params["ybeam"] = data_collection.y_beam
        params["xtal_snapshot1"] = data_collection.xtal_snapshots_1
        params["xtal_snapshot2"] = data_collection.xtal_snapshots_2
        params["xtal_snapshot3"] = data_collection.xtal_snapshots_3
        params["synchrotron_mode"] = data_collection.synchrotron_mode
        params["undulator_gap1"] = data_collection.undulator_gap
        params["starttime"] = data_collection.start_time
        params["endtime"] = data_collection.end_time
        params["run_status"] = data_collection.run_status
        params["file_template"] = data_collection.file_template
        params["binning"] = data_collection.binning

        return mx_acquisition.upsert_data_collection(list(params.values()))


    def store_position_table(self, position: Position) -> int:
        mx_acquisition = self.conn.mx_acquisition

        params = mx_acquisition.get_dc_position_params()
        params["pos_x"] = position.position_x
        params["pos_y"] = position.position_y
        params["pos_z"] = position.position_z

        return mx_acquisition.update_dc_position(list(params.values()))


    def store_data_collection_group_table(self, data_collection_group: DataCollectionGroup) -> int:
        core = self.conn.core
        mx_acquisition = self.conn.mx_acquisition

        sessionid = core.retrieve_visit_id(data_collection_group.visit)

        params = mx_acquisition.get_data_collection_params()
        params["parentid"] = sessionid
        params["experimenttype"] = data_collection_group.experimenttype
        params["sampleid"] = data_collection_group.sample_id
        params["sample_barcode"] = data_collection_group.sample_barcode

        return mx_acquisition.upsert_data_collection_group(list(params.values()))
