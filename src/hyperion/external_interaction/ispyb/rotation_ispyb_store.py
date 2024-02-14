from __future__ import annotations

from typing import cast

import ispyb
from ispyb.connector.mysqlsp.main import ISPyBMySQLSPConnector as Connector

from hyperion.external_interaction.ispyb.ispyb_store import (
    DataCollectionInfo,
    IspybIds,
    StoreInIspyb,
)
from hyperion.log import ISPYB_LOGGER
from hyperion.parameters.internal_parameters import InternalParameters
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
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

    def _populate_data_collection_info(
        self, ispyb_params, detector_params, full_params
    ):
        return DataCollectionInfo(
            detector_params.omega_start,
            detector_params.run_number,  # type:ignore # the validator always makes this int
            self._get_xtal_snapshots(ispyb_params),
            full_params.experiment_params.get_num_images(),
            full_params.experiment_params.image_width,
            (
                full_params.experiment_params.omega_start
                + full_params.experiment_params.rotation_angle
            ),
            full_params.experiment_params.chi_start,
        )

    def _get_xtal_snapshots(self, ispyb_params):
        if ispyb_params.xtal_snapshots_omega_start:
            xtal_snapshots = ispyb_params.xtal_snapshots_omega_start[:3]
            ISPYB_LOGGER.info(
                f"Using rotation scan snapshots {xtal_snapshots} for ISPyB deposition"
            )
            return xtal_snapshots
        else:
            ISPYB_LOGGER.warning("No xtal snapshot paths sent to ISPyB!")

    @property
    def experiment_type(self):
        return self._experiment_type

    def _store_scan_data(
        self, conn: Connector, full_params, ispyb_params, detector_params
    ):
        assert (
            self._data_collection_group_id
        ), "Attempted to store scan data without a collection group"
        assert (
            self._data_collection_id
        ), "Attempted to store scan data without a collection"
        self._store_data_collection_group_table(
            conn,
            ispyb_params,
            detector_params,
            self._data_collection_group_id,
        )
        data_collection_info = self._populate_data_collection_info(
            ispyb_params, detector_params, full_params
        )
        self._store_data_collection_table(
            conn,
            self._data_collection_group_id,
            self._construct_comment,
            ispyb_params,
            detector_params,
            data_collection_info,
            self._data_collection_id,
        )
        self._store_position_table(conn, self._data_collection_id, ispyb_params)

        return self._data_collection_id, self._data_collection_group_id

    def begin_deposition(self, internal_params: InternalParameters) -> IspybIds:
        # prevent pyright + black fighting
        # fmt: off
        full_params = cast(RotationInternalParameters, internal_params)
        with ispyb.open(self.ISPYB_CONFIG_PATH) as conn:
            assert conn is not None
            ispyb_params = full_params.hyperion_params.ispyb_params
            detector_params = full_params.hyperion_params.detector_params
            if not self._data_collection_group_id:
                self._data_collection_group_id = self._store_data_collection_group_table(conn, ispyb_params,
                                                                                         detector_params)
            if not self._data_collection_id:
                data_collection_info = self._populate_data_collection_info(ispyb_params, detector_params,
                                                                           full_params)
                self._data_collection_id = self._store_data_collection_table(conn, self._data_collection_group_id,
                                                                             self._construct_comment,
                                                                             ispyb_params, detector_params,
                                                                             data_collection_info)
        return IspybIds(
            data_collection_group_id=self._data_collection_group_id,
            data_collection_ids=(self._data_collection_id,),
        )
        # fmt: on

    def update_deposition(self, internal_params) -> IspybIds:
        full_params = cast(RotationInternalParameters, internal_params)
        with ispyb.open(self.ISPYB_CONFIG_PATH) as conn:
            assert conn is not None, "Failed to connect to ISPyB"
            ids = self._store_scan_data(
                conn,
                full_params,
                full_params.hyperion_params.ispyb_params,
                full_params.hyperion_params.detector_params,
            )
            return IspybIds(
                data_collection_ids=(ids[0],), data_collection_group_id=ids[1]
            )

    def end_deposition(self, success: str, reason: str, internal_params):
        assert (
            self._data_collection_id is not None
        ), "Can't end ISPyB deposition, data_collection IDs is missing"
        full_params = cast(RotationInternalParameters, internal_params)
        self._end_deposition(
            self._data_collection_id,
            success,
            reason,
            full_params.hyperion_params.ispyb_params,
            full_params.hyperion_params.detector_params,
        )

    def _construct_comment(self) -> str:
        return "Hyperion rotation scan"
