from __future__ import annotations

from ispyb.connector.mysqlsp.main import ISPyBMySQLSPConnector as Connector

from hyperion.external_interaction.ispyb.data_model import (
    DataCollectionInfo,
    GridScanInfo,
    ScanDataInfo,
)
from hyperion.external_interaction.ispyb.gridscan_ispyb_store import (
    StoreGridscanInIspyb,
    _construct_comment_for_gridscan,
    populate_data_collection_grid_info,
)
from hyperion.external_interaction.ispyb.ispyb_store import (
    IspybIds,
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
        data_collection_group_id,
        data_collection_ids,
    ) -> IspybIds:
        assert (
            data_collection_group_id
        ), "Attempted to store scan data without a collection group"
        assert data_collection_ids, "Attempted to store scan data without a collection"
        assert ispyb_params is not None and detector_params is not None

        def comment_constructor():
            return _construct_comment_for_gridscan(
                full_params, ispyb_params, grid_scan_info
            )

        xy_data_collection_info = populate_remaining_data_collection_info(
            comment_constructor,
            data_collection_group_id,
            xy_data_collection_info,
            detector_params,
            ispyb_params,
        )
        xy_scan_data_info = ScanDataInfo(
            data_collection_info=xy_data_collection_info,
            data_collection_grid_info=populate_data_collection_grid_info(
                full_params, grid_scan_info, ispyb_params
            ),
            data_collection_position_info=populate_data_collection_position_info(
                ispyb_params
            ),
        )

        data_collection_id, grid_id = self._store_single_scan_data(
            conn, xy_scan_data_info, data_collection_ids[0]
        )

        return IspybIds(
            data_collection_group_id=data_collection_group_id,
            data_collection_ids=(data_collection_id,),
            grid_ids=(grid_id,),
        )
