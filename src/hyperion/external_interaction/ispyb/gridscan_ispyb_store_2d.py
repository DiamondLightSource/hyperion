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
            self.data_collection_group_id
        ), "Attempted to store scan data without a collection group"
        assert (
            self.data_collection_ids
        ), "Attempted to store scan data without a collection"

        self._store_data_collection_group_table(conn, self.data_collection_group_id)

        data_collection_id = self._store_data_collection_table(
            conn, self.data_collection_group_id, self.data_collection_ids[0]
        )

        self._store_position_table(conn, data_collection_id)

        grid_id = self._store_grid_info_table(conn, data_collection_id)

        return [data_collection_id], [grid_id], self.data_collection_group_id
