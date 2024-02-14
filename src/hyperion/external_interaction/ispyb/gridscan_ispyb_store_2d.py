from __future__ import annotations

from ispyb.connector.mysqlsp.main import ISPyBMySQLSPConnector as Connector

from hyperion.external_interaction.ispyb.gridscan_ispyb_store import (
    GridScanInfo,
    StoreGridscanInIspyb,
)
from hyperion.external_interaction.ispyb.ispyb_store import DataCollectionInfo, IspybIds


class Store2DGridscanInIspyb(StoreGridscanInIspyb):
    def __init__(self, ispyb_config: str):
        super().__init__(ispyb_config)

    @property
    def experiment_type(self) -> str:
        return "mesh"

    def _store_scan_data(
        self,
        conn: Connector,
        xy_data_collection_info: DataCollectionInfo,
        grid_scan_info: GridScanInfo,
        ispyb_params,
        detector_params,
        full_params,
    ) -> IspybIds:
        assert (
            self._data_collection_group_id
        ), "Attempted to store scan data without a collection group"
        assert (
            self._data_collection_ids
        ), "Attempted to store scan data without a collection"

        self._store_data_collection_group_table(
            conn,
            ispyb_params,
            detector_params,
            self._data_collection_group_id,
        )

        def comment_constructor():
            return self._construct_comment(ispyb_params, full_params, grid_scan_info)

        collection_id = self._data_collection_ids[0]
        assert ispyb_params is not None and detector_params is not None
        params = self.fill_common_data_collection_params(
            comment_constructor,
            conn,
            self._data_collection_group_id,
            collection_id,
            detector_params,
            ispyb_params,
            xy_data_collection_info,
        )
        data_collection_id = self._upsert_data_collection(conn, params)

        self._store_position_table(conn, data_collection_id, ispyb_params)

        grid_id = self._store_grid_info_table(
            conn, data_collection_id, grid_scan_info, full_params, ispyb_params
        )

        return IspybIds(
            data_collection_group_id=self._data_collection_group_id,
            data_collection_ids=(data_collection_id,),
            grid_ids=(grid_id,),
        )
