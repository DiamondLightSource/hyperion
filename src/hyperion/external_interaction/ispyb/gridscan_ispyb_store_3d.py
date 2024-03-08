from __future__ import annotations

from ispyb.connector.mysqlsp.main import ISPyBMySQLSPConnector as Connector

from hyperion.external_interaction.ispyb.gridscan_ispyb_store import (
    StoreGridscanInIspyb,
)
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)


class Store3DGridscanInIspyb(StoreGridscanInIspyb):
    def __init__(self, ispyb_config: str, parameters: GridscanInternalParameters):
        super().__init__(ispyb_config, "Mesh3D", parameters)

    def _store_scan_data(self, conn: Connector):
        assert (
            self._data_collection_group_id
        ), "Attempted to store scan data without a collection group"
        assert (
            self._data_collection_ids
        ), "Attempted to store scan data without at least one collection"

        self._store_data_collection_group_table(conn, self._data_collection_group_id)

        data_collection_group_id = self._data_collection_group_id
        if len(self._data_collection_ids) != 1:
            data_collection_id_1 = self._store_data_collection_table(
                conn, data_collection_group_id
            )
        else:
            data_collection_id_1 = self._store_data_collection_table(
                conn, data_collection_group_id, self._data_collection_ids[0]
            )

        self._store_position_table(conn, data_collection_id_1)

        grid_id_1 = self._store_grid_info_table(conn, data_collection_id_1)

        self.__prepare_second_scan_params()

        data_collection_id_2 = self._store_data_collection_table(
            conn, data_collection_group_id
        )

        self._store_position_table(conn, data_collection_id_2)

        grid_id_2 = self._store_grid_info_table(conn, data_collection_id_2)

        return (
            [data_collection_id_1, data_collection_id_2],
            [grid_id_1, grid_id_2],
            data_collection_group_id,
        )

    def __prepare_second_scan_params(self):
        assert (
            self._omega_start is not None
            and self._run_number is not None
            and self._ispyb_params is not None
            and self.full_params is not None
        ), "StoreGridscanInIspyb failed to get parameters"
        self._omega_start += 90
        self._run_number += 1
        self._xtal_snapshots = self._ispyb_params.xtal_snapshots_omega_end or []
        self.upper_left = [
            int(self._ispyb_params.upper_left[0]),
            int(self._ispyb_params.upper_left[2]),
        ]
        self.y_steps = self.full_params.experiment_params.z_steps
        self.y_step_size = self.full_params.experiment_params.z_step_size
