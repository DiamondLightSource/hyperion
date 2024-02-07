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


class Store3DGridscanInIspyb(StoreGridscanInIspyb):
    def __init__(self, ispyb_config: str, parameters: GridscanInternalParameters):
        super().__init__(ispyb_config, "Mesh3D", parameters)

    def begin_deposition(self) -> IspybIds:
        # fmt: off
        with ispyb.open(self.ISPYB_CONFIG_PATH) as conn:
            self.detector_params = (  # pyright: ignore
                self.full_params.hyperion_params.detector_params
            )
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
        ), "Attempted to store scan data without at least one collection"

        data_collection_group_id = self.data_collection_group_id
        if len(self.data_collection_ids) != 1:
            data_collection_id_1 = self._store_data_collection_table(
                conn, data_collection_group_id
            )
        else:
            data_collection_id_1 = self._store_data_collection_table(
                conn, data_collection_group_id, self.data_collection_ids[0]
            )

        self._store_position_table(conn, data_collection_id_1)

        grid_id_1 = self._store_grid_info_table(conn, data_collection_id_1)

        self.__prepare_second_scan_params()

        data_collection_id_2 = self._store_data_collection_table(
            conn, data_collection_group_id
        )

        self._store_position_table(conn, data_collection_id_2)

        grid_id_2 = self._store_grid_info_table(conn, data_collection_id_2)

        return (
            [data_collection_id_1, data_collection_id_2],
            [grid_id_1, grid_id_2],
            data_collection_group_id,
        )

    def __prepare_second_scan_params(self):
        assert (
            self.omega_start is not None
            and self.run_number is not None
            and self.ispyb_params is not None
            and self.full_params is not None
        ), "StoreGridscanInIspyb failed to get parameters"
        self.omega_start += 90
        self.run_number += 1
        self.xtal_snapshots = self.ispyb_params.xtal_snapshots_omega_end or []
        self.upper_left = [
            int(self.ispyb_params.upper_left[0]),
            int(self.ispyb_params.upper_left[2]),
        ]
        self.y_steps = self.full_params.experiment_params.z_steps
        self.y_step_size = self.full_params.experiment_params.z_step_size
