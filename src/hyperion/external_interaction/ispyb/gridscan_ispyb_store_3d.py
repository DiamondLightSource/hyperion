from __future__ import annotations

from ispyb.connector.mysqlsp.main import ISPyBMySQLSPConnector as Connector

from hyperion.external_interaction.ispyb.gridscan_ispyb_store import (
    GridScanState,
    StoreGridscanInIspyb,
)
from hyperion.external_interaction.ispyb.ispyb_store import DataCollectionInfo
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)


class Store3DGridscanInIspyb(StoreGridscanInIspyb):
    def __init__(self, ispyb_config: str, parameters: GridscanInternalParameters):
        super().__init__(ispyb_config, parameters)

    @property
    def experiment_type(self):
        return "Mesh3D"

    def _store_scan_data(
        self, conn: Connector, xy_data_collection_info: DataCollectionInfo
    ):
        assert (
            self._data_collection_group_id
        ), "Attempted to store scan data without a collection group"
        assert (
            self._data_collection_ids
        ), "Attempted to store scan data without at least one collection"

        self._store_data_collection_group_table(
            conn,
            self._ispyb_params,
            self._detector_params,
            self._data_collection_group_id,
        )

        data_collection_group_id = self._data_collection_group_id
        xy_data_collection_info = self.with_axis_info(xy_data_collection_info)
        if len(self._data_collection_ids) != 1:
            data_collection_id_1 = self._store_data_collection_table(
                conn,
                data_collection_group_id,
                lambda: self._construct_comment(
                    self._ispyb_params, self.full_params, self._grid_scan_state
                ),
                self._ispyb_params,
                self._detector_params,
                xy_data_collection_info,
            )
        else:
            data_collection_id_1 = self._store_data_collection_table(
                conn,
                data_collection_group_id,
                lambda: self._construct_comment(
                    self._ispyb_params, self.full_params, self._grid_scan_state
                ),
                self._ispyb_params,
                self._detector_params,
                xy_data_collection_info,
                self._data_collection_ids[0],
            )

        self._store_position_table(conn, data_collection_id_1, self._ispyb_params)

        grid_id_1 = self._store_grid_info_table(conn, data_collection_id_1)

        xz_data_collection_info = self.__prepare_second_scan_params(
            xy_data_collection_info
        )

        xz_data_collection_info = self.with_axis_info(xz_data_collection_info)
        data_collection_id_2 = self._store_data_collection_table(
            conn,
            data_collection_group_id,
            lambda: self._construct_comment(
                self._ispyb_params, self.full_params, self._grid_scan_state
            ),
            self._ispyb_params,
            self._detector_params,
            xz_data_collection_info,
        )

        self._store_position_table(conn, data_collection_id_2, self._ispyb_params)

        grid_id_2 = self._store_grid_info_table(conn, data_collection_id_2)

        return (
            [data_collection_id_1, data_collection_id_2],
            [grid_id_1, grid_id_2],
            data_collection_group_id,
        )

    def __prepare_second_scan_params(
        self, xy_data_collection_info: DataCollectionInfo
    ) -> DataCollectionInfo:
        assert (
            xy_data_collection_info.omega_start is not None
            and xy_data_collection_info.run_number is not None
            and self._ispyb_params is not None
            and self.full_params is not None
        ), "StoreGridscanInIspyb failed to get parameters"
        omega_start = xy_data_collection_info.omega_start + 90
        run_number = xy_data_collection_info.run_number + 1
        xtal_snapshots = self._ispyb_params.xtal_snapshots_omega_end or []
        self._grid_scan_state = GridScanState(
            [
                int(self._ispyb_params.upper_left[0]),
                int(self._ispyb_params.upper_left[2]),
            ],
            self.full_params.experiment_params.z_steps,
            self.full_params.experiment_params.z_step_size,
        )
        return DataCollectionInfo(omega_start, run_number, xtal_snapshots)
