from __future__ import annotations

from ispyb.connector.mysqlsp.main import ISPyBMySQLSPConnector as Connector

from hyperion.external_interaction.ispyb.gridscan_ispyb_store import (
    StoreGridscanInIspyb,
)
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)


class Store2DGridscanInIspyb(StoreGridscanInIspyb):
    def __init__(self, ispyb_config: str, parameters: GridscanInternalParameters):
        super().__init__(ispyb_config, "mesh", parameters)

    def _store_scan_data(self, conn: Connector):
        assert (
            self._data_collection_group_id
        ), "Attempted to store scan data without a collection group"
        assert (
            self._data_collection_ids
        ), "Attempted to store scan data without a collection"

        self._store_data_collection_group_table(
            conn,
            self._ispyb_params,
            self._detector_params,
            self._data_collection_group_id,
        )

        data_collection_id = self._store_data_collection_table(
            conn,
            self._data_collection_group_id,
            lambda: self._construct_comment(
                self._ispyb_params,
                self.full_params,
                self.upper_left,
                self.y_step_size,
                self.y_steps,
            ),
            self._ispyb_params,
            self._detector_params,
            self._omega_start,
            self._run_number,
            self._xtal_snapshots,
            self._data_collection_ids[0],
        )

        self._store_position_table(conn, data_collection_id, self._ispyb_params)

        grid_id = self._store_grid_info_table(conn, data_collection_id)

        return [data_collection_id], [grid_id], self._data_collection_group_id
