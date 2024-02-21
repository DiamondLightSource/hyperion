from __future__ import annotations

import ispyb

from hyperion.external_interaction.ispyb.data_model import (
    DataCollectionGroupInfo,
    ScanDataInfo,
)
from hyperion.external_interaction.ispyb.ispyb_store import (
    IspybIds,
    StoreInIspyb,
)


class StoreRotationInIspyb(StoreInIspyb):
    def __init__(
        self,
        ispyb_config,
        datacollection_group_id: int | None = None,
        experiment_type: str = "SAD",
    ) -> None:
        super().__init__(ispyb_config)
        self._experiment_type = experiment_type
        self._data_collection_id: int | None = None
        self._data_collection_group_id = datacollection_group_id

    @property
    def experiment_type(self):
        return self._experiment_type

    def begin_deposition(
        self,
        data_collection_group_info: DataCollectionGroupInfo,
        scan_data_info: ScanDataInfo,
    ) -> IspybIds:
        # prevent pyright + black fighting
        # fmt: off
        with ispyb.open(self.ISPYB_CONFIG_PATH) as conn:
            assert conn is not None
            if not self._data_collection_group_id:
                self._data_collection_group_id = self._store_data_collection_group_table(conn,
                                                                                         data_collection_group_info)
            if not self._data_collection_id:
                scan_data_info.data_collection_info.parent_id = self._data_collection_group_id
                self._data_collection_id = self._store_data_collection_table(conn, None, scan_data_info.data_collection_info)
        return IspybIds(
            data_collection_group_id=self._data_collection_group_id,
            data_collection_ids=(self._data_collection_id,),
        )
        # fmt: on

    def update_deposition(
        self,
        ispyb_ids: IspybIds,
        data_collection_group_info: DataCollectionGroupInfo,
        scan_data_info: ScanDataInfo,
    ) -> IspybIds:
        with ispyb.open(self.ISPYB_CONFIG_PATH) as conn:
            assert conn is not None, "Failed to connect to ISPyB"
            assert (
                ispyb_ids.data_collection_group_id
            ), "Attempted to store scan data without a collection group"
            assert (
                ispyb_ids.data_collection_ids
            ), "Attempted to store scan data without a collection"
            self._store_data_collection_group_table(
                conn, data_collection_group_info, ispyb_ids.data_collection_group_id
            )
            self._data_collection_id, _ = self._store_single_scan_data(
                conn, scan_data_info, ispyb_ids.data_collection_ids[0]
            )
            return IspybIds(
                data_collection_ids=(self._data_collection_id,),
                data_collection_group_id=self._data_collection_group_id,
            )
