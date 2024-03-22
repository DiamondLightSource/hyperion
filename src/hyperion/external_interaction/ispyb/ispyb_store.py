from __future__ import annotations

from abc import ABC
from dataclasses import asdict
from itertools import zip_longest
from typing import TYPE_CHECKING, Optional, Sequence, Tuple

import ispyb
import ispyb.sqlalchemy
from ispyb.connector.mysqlsp.main import ISPyBMySQLSPConnector as Connector
from ispyb.sp.mxacquisition import MXAcquisition
from ispyb.strictordereddict import StrictOrderedDict
from pydantic import BaseModel

from hyperion.external_interaction.ispyb.data_model import (
    DataCollectionGroupInfo,
    DataCollectionInfo,
    ExperimentType,
    ScanDataInfo,
)
from hyperion.external_interaction.ispyb.ispyb_utils import (
    get_current_time_string,
    get_session_id_from_visit,
)
from hyperion.log import ISPYB_LOGGER
from hyperion.tracing import TRACER

if TYPE_CHECKING:
    pass

I03_EIGER_DETECTOR = 78
EIGER_FILE_SUFFIX = "h5"


class IspybIds(BaseModel):
    data_collection_ids: tuple[int, ...] = ()
    data_collection_group_id: int | None = None
    grid_ids: tuple[int, ...] = ()


class StoreInIspyb(ABC):
    def __init__(self, ispyb_config: str, experiment_type: ExperimentType) -> None:
        self.ISPYB_CONFIG_PATH: str = ispyb_config
        self._data_collection_group_id: int | None
        self._experiment_type = experiment_type

    @property
    def experiment_type(self) -> str:
        return self._experiment_type.value

    def begin_deposition(
        self,
        data_collection_group_info: DataCollectionGroupInfo,
        scan_data_info: ScanDataInfo,
    ) -> IspybIds:
        ispyb_ids = IspybIds()
        if scan_data_info.data_collection_info:
            ispyb_ids.data_collection_group_id = (
                scan_data_info.data_collection_info.parent_id
            )

        return self._begin_or_update_deposition(
            ispyb_ids, data_collection_group_info, [scan_data_info]
        )

    def update_deposition(
        self,
        ispyb_ids,
        data_collection_group_info: DataCollectionGroupInfo,
        scan_data_infos: Sequence[ScanDataInfo],
    ):
        assert (
            ispyb_ids.data_collection_group_id
        ), "Attempted to store scan data without a collection group"
        assert (
            ispyb_ids.data_collection_ids
        ), "Attempted to store scan data without a collection"
        return self._begin_or_update_deposition(
            ispyb_ids, data_collection_group_info, scan_data_infos
        )

    def _begin_or_update_deposition(
        self, ispyb_ids, data_collection_group_info, scan_data_infos
    ):
        with ispyb.open(self.ISPYB_CONFIG_PATH) as conn:
            assert conn is not None, "Failed to connect to ISPyB"

            ispyb_ids.data_collection_group_id = (
                self._store_data_collection_group_table(
                    conn, data_collection_group_info, ispyb_ids.data_collection_group_id
                )
            )

            grid_ids = []
            data_collection_ids_out = []
            for scan_data_info, data_collection_id in zip_longest(
                scan_data_infos, ispyb_ids.data_collection_ids
            ):
                if (
                    scan_data_info.data_collection_info
                    and not scan_data_info.data_collection_info.parent_id
                ):
                    scan_data_info.data_collection_info.parent_id = (
                        ispyb_ids.data_collection_group_id
                    )

                data_collection_id, grid_id = self._store_single_scan_data(
                    conn, scan_data_info, data_collection_id
                )
                data_collection_ids_out.append(data_collection_id)
                if grid_id:
                    grid_ids.append(grid_id)
            ispyb_ids = IspybIds(
                data_collection_ids=tuple(data_collection_ids_out),
                grid_ids=tuple(grid_ids),
                data_collection_group_id=ispyb_ids.data_collection_group_id,
            )
        return ispyb_ids

    def end_deposition(self, ispyb_ids: IspybIds, success: str, reason: str):
        assert (
            ispyb_ids.data_collection_ids
        ), "Can't end ISPyB deposition, data_collection IDs are missing"
        assert (
            ispyb_ids.data_collection_group_id is not None
        ), "Cannot end ISPyB deposition without data collection group ID"

        for id_ in ispyb_ids.data_collection_ids:
            ISPYB_LOGGER.info(
                f"End ispyb deposition with status '{success}' and reason '{reason}'."
            )
            if success == "fail" or success == "abort":
                run_status = "DataCollection Unsuccessful"
            else:
                run_status = "DataCollection Successful"
            current_time = get_current_time_string()
            self._update_scan_with_end_time_and_status(
                current_time,
                run_status,
                reason,
                id_,
                ispyb_ids.data_collection_group_id,
            )

    def append_to_comment(
        self, data_collection_id: int, comment: str, delimiter: str = " "
    ) -> None:
        with ispyb.open(self.ISPYB_CONFIG_PATH) as conn:
            assert conn is not None, "Failed to connect to ISPyB!"
            mx_acquisition: MXAcquisition = conn.mx_acquisition
            mx_acquisition.update_data_collection_append_comments(
                data_collection_id, comment, delimiter
            )

    def _update_scan_with_end_time_and_status(
        self,
        end_time: str,
        run_status: str,
        reason: str,
        data_collection_id: int,
        data_collection_group_id: int,
    ) -> None:
        if reason is not None and reason != "":
            self.append_to_comment(data_collection_id, f"{run_status} reason: {reason}")

        with ispyb.open(self.ISPYB_CONFIG_PATH) as conn:
            assert conn is not None, "Failed to connect to ISPyB!"

            mx_acquisition: MXAcquisition = conn.mx_acquisition

            params = mx_acquisition.get_data_collection_params()
            params["id"] = data_collection_id
            params["parentid"] = data_collection_group_id
            params["endtime"] = end_time
            params["run_status"] = run_status

            mx_acquisition.upsert_data_collection(list(params.values()))

    def _store_position_table(
        self, conn: Connector, dc_pos_info, data_collection_id
    ) -> int:
        mx_acquisition: MXAcquisition = conn.mx_acquisition

        params = mx_acquisition.get_dc_position_params()
        params["id"] = data_collection_id
        params |= asdict(dc_pos_info)

        return mx_acquisition.update_dc_position(list(params.values()))

    def _store_data_collection_group_table(
        self,
        conn: Connector,
        dcg_info: DataCollectionGroupInfo,
        data_collection_group_id: Optional[int] = None,
    ) -> int:
        mx_acquisition: MXAcquisition = conn.mx_acquisition

        params = mx_acquisition.get_data_collection_group_params()
        if data_collection_group_id:
            params["id"] = data_collection_group_id
        params["parent_id"] = get_session_id_from_visit(conn, dcg_info.visit_string)
        params |= {k: v for k, v in asdict(dcg_info).items() if k != "visit_string"}

        return self._upsert_data_collection_group(conn, params)

    def _store_data_collection_table(
        self, conn, data_collection_id, data_collection_info
    ):
        params = self._fill_common_data_collection_params(
            conn, data_collection_id, data_collection_info
        )
        return self._upsert_data_collection(conn, params)

    def _store_single_scan_data(
        self, conn, scan_data_info, data_collection_id=None
    ) -> Tuple[int, Optional[int]]:
        data_collection_id = self._store_data_collection_table(
            conn, data_collection_id, scan_data_info.data_collection_info
        )

        if scan_data_info.data_collection_position_info:
            self._store_position_table(
                conn,
                scan_data_info.data_collection_position_info,
                data_collection_id,
            )

        grid_id = None
        if scan_data_info.data_collection_grid_info:
            grid_id = self._store_grid_info_table(
                conn,
                data_collection_id,
                scan_data_info.data_collection_grid_info,
            )
        return data_collection_id, grid_id

    def _store_grid_info_table(
        self, conn: Connector, ispyb_data_collection_id: int, dc_grid_info
    ) -> int:
        mx_acquisition: MXAcquisition = conn.mx_acquisition
        params = mx_acquisition.get_dc_grid_params()
        params |= dc_grid_info.as_dict()
        params["parentid"] = ispyb_data_collection_id
        return mx_acquisition.upsert_dc_grid(list(params.values()))

    def _fill_common_data_collection_params(
        self, conn, data_collection_id, data_collection_info: DataCollectionInfo
    ) -> StrictOrderedDict:
        mx_acquisition: MXAcquisition = conn.mx_acquisition
        params = mx_acquisition.get_data_collection_params()

        if data_collection_id:
            params["id"] = data_collection_id
        assert data_collection_info.visit_string
        params["visit_id"] = get_session_id_from_visit(
            conn, data_collection_info.visit_string
        )
        params |= {
            k: v for k, v in asdict(data_collection_info).items() if k != "visit_string"
        }

        return params

    @staticmethod
    @TRACER.start_as_current_span("_upsert_data_collection_group")
    def _upsert_data_collection_group(
        conn: Connector, params: StrictOrderedDict
    ) -> int:
        return conn.mx_acquisition.upsert_data_collection_group(list(params.values()))

    @staticmethod
    @TRACER.start_as_current_span("_upsert_data_collection")
    def _upsert_data_collection(conn: Connector, params: StrictOrderedDict) -> int:
        return conn.mx_acquisition.upsert_data_collection(list(params.values()))
