from __future__ import annotations

from ispyb.connector.mysqlsp.main import ISPyBMySQLSPConnector as Connector

from hyperion.external_interaction.ispyb.data_model import (
    DataCollectionInfo,
    GridScanInfo,
)
from hyperion.external_interaction.ispyb.gridscan_ispyb_store import (
    StoreGridscanInIspyb,
    _construct_comment_for_gridscan,
    populate_data_collection_grid_info,
)
from hyperion.external_interaction.ispyb.ispyb_store import (
    IspybIds,
    populate_data_collection_group,
    populate_data_collection_position_info,
    populate_remaining_data_collection_info,
)


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
        full_params,
        ispyb_params,
        detector_params,
    ) -> IspybIds:
        assert (
            self._data_collection_group_id
        ), "Attempted to store scan data without a collection group"
        assert (
            self._data_collection_ids
        ), "Attempted to store scan data without a collection"
        assert ispyb_params is not None and detector_params is not None

        dcg_info = populate_data_collection_group(
            self.experiment_type, conn, detector_params, ispyb_params
        )
        self._store_data_collection_group_table(
            conn, dcg_info, self._data_collection_group_id
        )

        def comment_constructor():
            return _construct_comment_for_gridscan(
                full_params, ispyb_params, grid_scan_info
            )

        collection_id = self._data_collection_ids[0]
        populate_remaining_data_collection_info(
            comment_constructor,
            conn,
            self._data_collection_group_id,
            xy_data_collection_info,
            detector_params,
            ispyb_params,
        )
        params = self.fill_common_data_collection_params(
            conn, collection_id, xy_data_collection_info
        )
        data_collection_id = self._upsert_data_collection(conn, params)

        dc_pos_info = populate_data_collection_position_info(ispyb_params)
        self._store_position_table(conn, dc_pos_info, data_collection_id)

        grid_id = self._store_grid_info_table(
            conn,
            data_collection_id,
            populate_data_collection_grid_info(
                full_params, grid_scan_info, ispyb_params
            ),
        )

        return IspybIds(
            data_collection_group_id=self._data_collection_group_id,
            data_collection_ids=(data_collection_id,),
            grid_ids=(grid_id,),
        )
