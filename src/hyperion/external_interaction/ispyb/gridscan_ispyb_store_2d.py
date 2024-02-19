from __future__ import annotations

from itertools import zip_longest
from typing import Sequence

from ispyb.connector.mysqlsp.main import ISPyBMySQLSPConnector as Connector

from hyperion.external_interaction.ispyb.data_model import (
    ScanDataInfo,
)
from hyperion.external_interaction.ispyb.gridscan_ispyb_store import (
    StoreGridscanInIspyb,
)
from hyperion.external_interaction.ispyb.ispyb_store import (
    IspybIds,
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
        scan_data_infos: Sequence[ScanDataInfo],
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

        grid_ids = []
        data_collection_ids_out = []
        for scan_data_info, data_collection_id in zip_longest(
            scan_data_infos, data_collection_ids
        ):
            data_collection_id, grid_id = self._store_single_scan_data(
                conn, scan_data_info, data_collection_id
            )
            data_collection_ids_out.append(data_collection_id)
            grid_ids.append(grid_id)

        return IspybIds(
            data_collection_ids=tuple(data_collection_ids_out),
            grid_ids=tuple(grid_ids),
            data_collection_group_id=data_collection_group_id,
        )
