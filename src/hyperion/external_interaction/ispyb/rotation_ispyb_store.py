from __future__ import annotations

from typing import Any

import ispyb
from ispyb.connector.mysqlsp.main import ISPyBMySQLSPConnector as Connector

from hyperion.external_interaction.ispyb.ispyb_dataclass import RotationIspybParams
from hyperion.external_interaction.ispyb.ispyb_store import (
    IspybIds,
    StoreInIspyb,
)
from hyperion.log import ISPYB_LOGGER
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)


class StoreRotationInIspyb(StoreInIspyb):
    def __init__(
        self,
        ispyb_config,
        parameters: RotationInternalParameters,
        datacollection_group_id: int | None = None,
    ) -> None:
        super().__init__(ispyb_config, "SAD")
        self.full_params: RotationInternalParameters = parameters
        self.ispyb_params: RotationIspybParams = parameters.hyperion_params.ispyb_params
        self.detector_params = parameters.hyperion_params.detector_params
        self.run_number = (
            self.detector_params.run_number
        )  # type:ignore # the validator always makes this int
        self.omega_start = self.detector_params.omega_start
        self.data_collection_id: int | None = None
        self.data_collection_group_id = datacollection_group_id

        if self.ispyb_params.xtal_snapshots_omega_start:
            self.xtal_snapshots = self.ispyb_params.xtal_snapshots_omega_start[:3]
            ISPYB_LOGGER.info(
                f"Using rotation scan snapshots {self.xtal_snapshots} for ISPyB deposition"
            )
        else:
            self.xtal_snapshots = []
            ISPYB_LOGGER.warning("No xtal snapshot paths sent to ISPyB!")

    def _mutate_data_collection_params_for_experiment(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        assert self.full_params is not None
        params["axis_range"] = self.full_params.experiment_params.image_width
        params["axis_end"] = (
            self.full_params.experiment_params.omega_start
            + self.full_params.experiment_params.rotation_angle
        )
        params["n_images"] = self.full_params.experiment_params.get_num_images()
        params["kappastart"] = self.full_params.experiment_params.chi_start
        return params

    def _store_scan_data(self, conn: Connector):
        assert (
            self.data_collection_group_id
        ), "Attempted to store scan data without a collection group"
        assert (
            self.data_collection_id
        ), "Attempted to store scan data without a collection"
        self._store_data_collection_group_table(conn, self.data_collection_group_id)
        self._store_data_collection_table(
            conn, self.data_collection_group_id, self.data_collection_id
        )
        self._store_position_table(conn, self.data_collection_id)

        return self.data_collection_id, self.data_collection_group_id

    def begin_deposition(self) -> IspybIds:
        # prevent pyright + black fighting
        # fmt: off
        with ispyb.open(self.ISPYB_CONFIG_PATH) as conn:
            if not self.data_collection_group_id:
                self.data_collection_group_id = self._store_data_collection_group_table(
                    conn  # type: ignore
                )
            if not self.data_collection_id:
                self.data_collection_id = self._store_data_collection_table(
                    conn, self.data_collection_group_id  # type: ignore
                )
        return IspybIds(
            data_collection_group_id=self.data_collection_group_id,
            data_collection_ids=self.data_collection_id,
        )
        # fmt: on

    def update_deposition(self) -> IspybIds:
        with ispyb.open(self.ISPYB_CONFIG_PATH) as conn:
            assert conn is not None, "Failed to connect to ISPyB"
            ids = self._store_scan_data(conn)
            return IspybIds(data_collection_ids=ids[0], data_collection_group_id=ids[1])

    def end_deposition(self, success: str, reason: str):
        assert (
            self.data_collection_id is not None
        ), "Can't end ISPyB deposition, data_collection IDs is missing"
        self._end_deposition(self.data_collection_id, success, reason)

    def _construct_comment(self) -> str:
        return "Hyperion rotation scan"
