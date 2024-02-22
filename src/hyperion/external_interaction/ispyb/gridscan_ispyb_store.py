from __future__ import annotations

from abc import ABC
from itertools import zip_longest
from typing import Sequence

import ispyb
from ispyb.connector.mysqlsp.main import ISPyBMySQLSPConnector as Connector

from hyperion.external_interaction.ispyb.data_model import (
    DataCollectionGroupInfo,
    ScanDataInfo,
)
from hyperion.external_interaction.ispyb.ispyb_store import (
    IspybIds,
    StoreInIspyb,
)


class StoreGridscanInIspyb(StoreInIspyb, ABC):
    def __init__(self, ispyb_config: str) -> None:
        super().__init__(ispyb_config)

    def begin_deposition(
        self,
        data_collection_group_info: DataCollectionGroupInfo,
        scan_data_info: ScanDataInfo,
    ) -> IspybIds:
        with ispyb.open(self.ISPYB_CONFIG_PATH) as conn:
            assert conn is not None
            data_collection_group_id = self._store_data_collection_group_table(
                conn, data_collection_group_info
            )
            scan_data_info.data_collection_info.parent_id = data_collection_group_id
            params = self.fill_common_data_collection_params(
                conn, None, scan_data_info.data_collection_info
            )
            data_collection_ids = (self._upsert_data_collection(conn, params),)
            return IspybIds(
                data_collection_group_id=data_collection_group_id,
                data_collection_ids=data_collection_ids,
            )

    def update_deposition(
        self,
        ispyb_ids,
        data_collection_group_info: DataCollectionGroupInfo,
        scan_data_infos: Sequence[ScanDataInfo],
    ):
        ispyb_ids = self._store_grid_scan(
            ispyb_ids.data_collection_group_id,
            data_collection_group_info,
            ispyb_ids.data_collection_ids,
            scan_data_infos,
        )
        return ispyb_ids

    def _store_grid_scan(
        self,
        data_collection_group_id,
        dcg_info,
        data_collection_ids,
        scan_data_infos: Sequence[ScanDataInfo],
    ) -> IspybIds:
        with ispyb.open(self.ISPYB_CONFIG_PATH) as conn:
            assert conn is not None, "Failed to connect to ISPyB"

            self._store_data_collection_group_table(
                conn, dcg_info, data_collection_group_id
            )

            return self._store_scan_data(
                conn, scan_data_infos, data_collection_group_id, data_collection_ids
            )

    def _store_scan_data(
        self,
        conn: Connector,
        scan_data_infos: Sequence[ScanDataInfo],
        data_collection_group_id,
        data_collection_ids,
    ) -> IspybIds:
        assert (
            data_collection_group_id
        ), "Attempted to store scan data without a collection group"
        assert data_collection_ids, "Attempted to store scan data without a collection"

        grid_ids = []
        data_collection_ids_out = []
        for scan_data_info, data_collection_id in zip_longest(
            scan_data_infos, data_collection_ids
        ):
            data_collection_id, grid_id = self._store_single_scan_data(
                conn, scan_data_info, data_collection_id
            )
            data_collection_ids_out.append(data_collection_id)
            if grid_id:
                grid_ids.append(grid_id)

        return IspybIds(
            data_collection_ids=tuple(data_collection_ids_out),
            grid_ids=tuple(grid_ids),
            data_collection_group_id=data_collection_group_id,
        )
