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
        super().__init__(ispyb_config, parameters)

    @property
    def experiment_type(self):
        return "mesh"

    def _store_scan_data(
        self,
        conn: Connector,
        xy_data_collection_info,
    ):
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

        def constructor():
            return self._construct_comment(
                self._ispyb_params, self.full_params, self._grid_scan_state
            )

        collection_id = self._data_collection_ids[0]
        assert self._ispyb_params is not None and self._detector_params is not None
        xy_data_collection_info = self.with_axis_info(xy_data_collection_info)
        params = self.fill_common_data_collection_params(
            constructor,
            conn,
            self._data_collection_group_id,
            collection_id,
            self._detector_params,
            self._ispyb_params,
            xy_data_collection_info,
        )
        data_collection_id = self._upsert_data_collection(conn, params)

        self._store_position_table(conn, data_collection_id, self._ispyb_params)

        grid_id = self._store_grid_info_table(conn, data_collection_id)

        return [data_collection_id], [grid_id], self._data_collection_group_id
