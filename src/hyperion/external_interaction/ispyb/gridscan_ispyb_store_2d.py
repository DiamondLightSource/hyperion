from __future__ import annotations

import ispyb
from ispyb.connector.mysqlsp.main import ISPyBMySQLSPConnector as Connector

from hyperion.external_interaction.ispyb.gridscan_ispyb_store import (
    StoreGridscanInIspyb,
)
from hyperion.external_interaction.ispyb.ispyb_store import (
    IspybIds,
)
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)


class Store2DGridscanInIspyb(StoreGridscanInIspyb):
    def __init__(self, ispyb_config: str, parameters: GridscanInternalParameters):
        super().__init__(ispyb_config, "mesh", parameters)

    def begin_deposition(self) -> IspybIds:
        # fmt: off
        with ispyb.open(self.ISPYB_CONFIG_PATH) as conn:
            self.detector_params = self.full_params.hyperion_params.detector_params  # type: ignore
            self.run_number = self.detector_params.run_number  # pyright: ignore
            self.data_collection_group_id = self._store_data_collection_group_table(
                conn  # pyright: ignore
            )
            self.xtal_snapshots = self.ispyb_params.xtal_snapshots_omega_start or []
            self.data_collection_ids = (
                self._store_data_collection_table(conn, self.data_collection_group_id),  # pyright: ignore
            )
            return IspybIds(
                data_collection_group_id=self.data_collection_group_id,
                data_collection_ids=self.data_collection_ids,
            )
        # fmt: on

    def _store_scan_data(self, conn: Connector):
        assert (
            self.data_collection_group_id
        ), "Attempted to store scan data without a collection group"
        assert (
            self.data_collection_ids
        ), "Attempted to store scan data without a collection"

        self._store_data_collection_group_table(conn)

        data_collection_id = self._store_data_collection_table(
            conn, self.data_collection_group_id, self.data_collection_ids[0]
        )

        self._store_position_table(conn, data_collection_id)

        grid_id = self._store_grid_info_table(conn, data_collection_id)

        return [data_collection_id], [grid_id], self.data_collection_group_id
