from __future__ import annotations

import ispyb
from ispyb.connector.mysqlsp.main import ISPyBMySQLSPConnector as Connector

from hyperion.external_interaction.ispyb.ispyb_dataclass import RotationIspybParams
from hyperion.external_interaction.ispyb.ispyb_store import (
    DataCollectionInfo,
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
        experiment_type: str = "SAD",
    ) -> None:
        super().__init__(ispyb_config)
        self._experiment_type = experiment_type
        self.full_params: RotationInternalParameters = parameters
        self._ispyb_params: RotationIspybParams = (  # pyright: ignore
            parameters.hyperion_params.ispyb_params
        )
        self._detector_params = parameters.hyperion_params.detector_params
        self._data_collection_id: int | None = None
        self._data_collection_group_id = datacollection_group_id

    def _populate_data_collection_info(self):
        return DataCollectionInfo(
            self._detector_params.omega_start,
            self._detector_params.run_number,  # type:ignore # the validator always makes this int
            self._get_xtal_snapshots(self._ispyb_params),
            self.full_params.experiment_params.get_num_images(),
            self.full_params.experiment_params.image_width,
            (
                self.full_params.experiment_params.omega_start
                + self.full_params.experiment_params.rotation_angle
            ),
            self.full_params.experiment_params.chi_start,
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

    def _store_scan_data(self, conn: Connector):
        assert (
            self._data_collection_group_id
        ), "Attempted to store scan data without a collection group"
        assert (
            self._data_collection_id
        ), "Attempted to store scan data without a collection"
        self._store_data_collection_group_table(
            conn,
            self._ispyb_params,
            self._detector_params,
            self._data_collection_group_id,
        )
        data_collection_info = self._populate_data_collection_info()
        self._store_data_collection_table(
            conn,
            self._data_collection_group_id,
            self._construct_comment,
            self._ispyb_params,
            self._detector_params,
            data_collection_info,
            self._data_collection_id,
        )
        self._store_position_table(conn, self._data_collection_id, self._ispyb_params)

        return self._data_collection_id, self._data_collection_group_id

    def begin_deposition(self) -> IspybIds:
        # prevent pyright + black fighting
        # fmt: off
        with ispyb.open(self.ISPYB_CONFIG_PATH) as conn:
            if not self._data_collection_group_id:
                self._data_collection_group_id = self._store_data_collection_group_table(conn, self._ispyb_params,
                                                                                         self._detector_params)
            if not self._data_collection_id:
                data_collection_info = self._populate_data_collection_info()
                self._data_collection_id = self._store_data_collection_table(conn, self._data_collection_group_id,
                                                                             self._construct_comment,
                                                                             self._ispyb_params, self._detector_params,
                                                                             data_collection_info)
        return IspybIds(
            data_collection_group_id=self._data_collection_group_id,
            data_collection_ids=(self._data_collection_id,),
        )
        # fmt: on

    def update_deposition(self) -> IspybIds:
        with ispyb.open(self.ISPYB_CONFIG_PATH) as conn:
            assert conn is not None, "Failed to connect to ISPyB"
            ids = self._store_scan_data(conn)
            return IspybIds(
                data_collection_ids=(ids[0],), data_collection_group_id=ids[1]
            )

    def end_deposition(self, success: str, reason: str):
        assert (
            self._data_collection_id is not None
        ), "Can't end ISPyB deposition, data_collection IDs is missing"
        self._end_deposition(self._data_collection_id, success, reason)

    def _construct_comment(self) -> str:
        return "Hyperion rotation scan"
