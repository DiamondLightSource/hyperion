import ispyb
from src.artemis.ispyb.ispyb_dataclasses import GridInfo, DataCollection

ISPYB_CONFIG_FILE = "/dls_sw/dasc/mariadb/credentials/ispyb-dev.cfg"


def store_grid_info_table(grid_info: GridInfo, visit: str) -> int:
    with ispyb.open(ISPYB_CONFIG_FILE) as conn:
        mx_acquisition = conn.mx_acquisition

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


def store_data_collection_table(data_collection: DataCollection) -> int:
    with ispyb.open(ISPYB_CONFIG_FILE) as conn:
        core = conn.core
        mx_acquisition = conn.mx_acquisition

        sessionid = core.retrieve_visit_id(data_collection.visit)

        params = mx_acquisition.get_data_collection_params()
        params["visitid"] = sessionid
