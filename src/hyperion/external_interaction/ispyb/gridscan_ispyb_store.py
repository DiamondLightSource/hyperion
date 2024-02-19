from __future__ import annotations

from abc import abstractmethod
from typing import Sequence, cast

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
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)


class StoreGridscanInIspyb(StoreInIspyb):
    def __init__(self, ispyb_config: str) -> None:
        super().__init__(ispyb_config)
        self._data_collection_ids: tuple[int, ...] | None = None
        self.grid_ids: tuple[int, ...] | None = None

    def begin_deposition(
        self,
        data_collection_group_info: DataCollectionGroupInfo = None,
        scan_data_info: ScanDataInfo = None,
    ) -> IspybIds:
        # fmt: off
        with ispyb.open(self.ISPYB_CONFIG_PATH) as conn:
            assert conn is not None
            self._data_collection_group_id = self._store_data_collection_group_table(conn, data_collection_group_info)
            scan_data_info.data_collection_info.parent_id = self._data_collection_group_id
            params = self.fill_common_data_collection_params(conn, None, scan_data_info.data_collection_info)
            self._data_collection_ids = (
                self._upsert_data_collection(conn, params),  # pyright: ignore
            )
            return IspybIds(
                data_collection_group_id=self._data_collection_group_id,
                data_collection_ids=self._data_collection_ids,
            )
        # fmt: on

    def update_deposition(
        self,
        internal_params,
        data_collection_group_info: DataCollectionGroupInfo = None,
        scan_data_infos: Sequence[ScanDataInfo] = (),
    ):
        full_params = cast(GridscanInternalParameters, internal_params)
        assert full_params is not None, "StoreGridscanInIspyb failed to get parameters."

        ispyb_ids = self._store_grid_scan(
            full_params,
            full_params.hyperion_params.ispyb_params,
            full_params.hyperion_params.detector_params,
            self._data_collection_group_id,
            data_collection_group_info,
            self._data_collection_ids,
            scan_data_infos,
        )
        self._data_collection_ids = ispyb_ids.data_collection_ids  # pyright: ignore
        self._data_collection_group_id = ispyb_ids.data_collection_group_id
        self.grid_ids = ispyb_ids.grid_ids
        return ispyb_ids

    def end_deposition(self, success: str, reason: str):
        assert (
            self._data_collection_ids
        ), "Can't end ISPyB deposition, data_collection IDs are missing"
        for id in self._data_collection_ids:
            self._end_deposition(id, success, reason)

    def _store_grid_scan(
        self,
        full_params: GridscanInternalParameters,
        ispyb_params,
        detector_params,
        data_collection_group_id,
        dcg_info,
        data_collection_ids,
        scan_data_infos: Sequence[ScanDataInfo],
    ) -> IspybIds:
        assert ispyb_params.upper_left is not None

        with ispyb.open(self.ISPYB_CONFIG_PATH) as conn:
            assert conn is not None, "Failed to connect to ISPyB"

            self._store_data_collection_group_table(
                conn, dcg_info, data_collection_group_id
            )

            return self._store_scan_data(
                conn, scan_data_infos, data_collection_group_id, data_collection_ids
            )

    @abstractmethod
    def _store_scan_data(
        self,
        conn: Connector,
        scan_data_infos: Sequence[ScanDataInfo],
        data_collection_group_id,
        data_collection_ids,
    ) -> IspybIds:
        pass
