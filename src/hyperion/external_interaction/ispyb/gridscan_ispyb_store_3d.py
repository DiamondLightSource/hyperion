from __future__ import annotations

from ispyb.connector.mysqlsp.main import ISPyBMySQLSPConnector as Connector

from hyperion.external_interaction.ispyb.gridscan_ispyb_store import (
    GridScanInfo,
    StoreGridscanInIspyb,
)
from hyperion.external_interaction.ispyb.ispyb_store import DataCollectionInfo, IspybIds


class Store3DGridscanInIspyb(StoreGridscanInIspyb):
    def __init__(self, ispyb_config: str):
        super().__init__(ispyb_config)

    @property
    def experiment_type(self):
        return "Mesh3D"

    def _store_scan_data(
        self,
        conn: Connector,
        xy_data_collection_info: DataCollectionInfo,
        grid_scan_info: GridScanInfo,
        full_params,
        ispyb_params,
        detector_params,
    ) -> IspybIds:
        assert (
            self._data_collection_group_id
        ), "Attempted to store scan data without a collection group"
        assert (
            self._data_collection_ids
        ), "Attempted to store scan data without at least one collection"

        self._store_data_collection_group_table(
            conn,
            ispyb_params,
            detector_params,
            self._data_collection_group_id,
        )

        data_collection_group_id = self._data_collection_group_id
        if len(self._data_collection_ids) != 1:
            data_collection_id_1 = self._store_data_collection_table(
                conn,
                data_collection_group_id,
                lambda: self._construct_comment(
                    full_params, ispyb_params, grid_scan_info
                ),
                ispyb_params,
                detector_params,
                xy_data_collection_info,
            )
        else:
            data_collection_id_1 = self._store_data_collection_table(
                conn,
                data_collection_group_id,
                lambda: self._construct_comment(
                    full_params, ispyb_params, grid_scan_info
                ),
                ispyb_params,
                detector_params,
                xy_data_collection_info,
                self._data_collection_ids[0],
            )

        self._store_position_table(conn, data_collection_id_1, ispyb_params)

        grid_id_1 = self._store_grid_info_table(
            conn,
            data_collection_id_1,
            grid_scan_info,
            full_params,
            ispyb_params,
        )

        grid_scan_info = GridScanInfo(
            [
                int(ispyb_params.upper_left[0]),
                int(ispyb_params.upper_left[2]),
            ],
            full_params.experiment_params.z_steps,
            full_params.experiment_params.z_step_size,
        )

        xz_data_collection_info = self._populate_xz_data_collection_info(
            xy_data_collection_info, grid_scan_info, full_params, ispyb_params
        )

        data_collection_id_2 = self._store_data_collection_table(
            conn,
            data_collection_group_id,
            lambda: self._construct_comment(full_params, ispyb_params, grid_scan_info),
            ispyb_params,
            detector_params,
            xz_data_collection_info,
        )

        self._store_position_table(conn, data_collection_id_2, ispyb_params)

        grid_id_2 = self._store_grid_info_table(
            conn,
            data_collection_id_2,
            grid_scan_info,
            full_params,
            ispyb_params,
        )

        return IspybIds(
            data_collection_ids=(data_collection_id_1, data_collection_id_2),
            grid_ids=(grid_id_1, grid_id_2),
            data_collection_group_id=data_collection_group_id,
        )

    def _populate_xz_data_collection_info(
        self,
        xy_data_collection_info: DataCollectionInfo,
        grid_scan_info: GridScanInfo,
        full_params,
        ispyb_params,
    ) -> DataCollectionInfo:
        assert (
            xy_data_collection_info.omega_start is not None
            and xy_data_collection_info.run_number is not None
            and ispyb_params is not None
            and full_params is not None
        ), "StoreGridscanInIspyb failed to get parameters"
        omega_start = xy_data_collection_info.omega_start + 90
        run_number = xy_data_collection_info.run_number + 1
        xtal_snapshots = ispyb_params.xtal_snapshots_omega_end or []
        info = DataCollectionInfo(
            omega_start,
            run_number,
            xtal_snapshots,
            full_params.experiment_params.x_steps * grid_scan_info.y_steps,
            0,
            omega_start,
        )
        return info
