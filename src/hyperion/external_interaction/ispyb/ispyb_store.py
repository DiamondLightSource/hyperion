from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict
from typing import TYPE_CHECKING, Optional, Tuple

import ispyb
import ispyb.sqlalchemy
from ispyb.connector.mysqlsp.main import ISPyBMySQLSPConnector as Connector
from ispyb.sp.mxacquisition import MXAcquisition
from ispyb.strictordereddict import StrictOrderedDict
from pydantic import BaseModel

from hyperion.external_interaction.ispyb.data_model import (
    DataCollectionGroupInfo,
    DataCollectionInfo,
    DataCollectionPositionInfo,
    ScanDataInfo,
)
from hyperion.external_interaction.ispyb.ispyb_utils import (
    get_current_time_string,
    get_session_id_from_visit,
    get_visit_string,
)
from hyperion.log import ISPYB_LOGGER
from hyperion.parameters.internal_parameters import InternalParameters
from hyperion.tracing import TRACER

if TYPE_CHECKING:
    pass

I03_EIGER_DETECTOR = 78
EIGER_FILE_SUFFIX = "h5"


class IspybIds(BaseModel):
    data_collection_ids: tuple[int, ...] = tuple()
    data_collection_group_id: int | None = None
    grid_ids: tuple[int, ...] | None = None


class StoreInIspyb(ABC):
    def __init__(self, ispyb_config: str) -> None:
        self.ISPYB_CONFIG_PATH: str = ispyb_config
        self._data_collection_group_id: int | None

    @property
    @abstractmethod
    def experiment_type(self) -> str:
        pass

    @abstractmethod
    def begin_deposition(
        self,
        internal_params: InternalParameters,
        data_collection_group_info: DataCollectionGroupInfo = None,
        scan_data_info: ScanDataInfo = None,
    ) -> IspybIds:
        pass

    @abstractmethod
    def update_deposition(self, internal_params: InternalParameters) -> IspybIds:
        pass

    @abstractmethod
    def end_deposition(
        self, success: str, reason: str, internal_params: InternalParameters
    ):
        pass

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

    def _end_deposition(self, dcid: int, success: str, reason: str):
        """Write the end of data_collection data.
        Args:
            success (str): The success of the run, could be fail or abort
            reason (str): If the run failed, the reason why
        """
        ISPYB_LOGGER.info(
            f"End ispyb deposition with status '{success}' and reason '{reason}'."
        )
        if success == "fail" or success == "abort":
            run_status = "DataCollection Unsuccessful"
        else:
            run_status = "DataCollection Successful"
        current_time = get_current_time_string()
        assert self._data_collection_group_id is not None
        self._update_scan_with_end_time_and_status(
            current_time, run_status, reason, dcid, self._data_collection_group_id
        )

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

        return conn.mx_acquisition.upsert_data_collection_group(list(params.values()))

    @staticmethod
    @TRACER.start_as_current_span("_upsert_data_collection")
    def _upsert_data_collection(conn: Connector, params: StrictOrderedDict) -> int:
        return conn.mx_acquisition.upsert_data_collection(list(params.values()))

    def _store_data_collection_table(
        self, conn, data_collection_id, data_collection_info
    ):
        params = self.fill_common_data_collection_params(
            conn, data_collection_id, data_collection_info
        )
        return self._upsert_data_collection(conn, params)

    def _store_single_scan_data(
        self, conn, scan_data_info, data_collection_id=None
    ) -> Tuple[int, int]:
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

    def fill_common_data_collection_params(
        self, conn, data_collection_id, data_collection_info: DataCollectionInfo
    ) -> DataCollectionInfo:
        mx_acquisition: MXAcquisition = conn.mx_acquisition
        params = mx_acquisition.get_data_collection_params()

        if data_collection_id:
            params["id"] = data_collection_id
        params["visit_id"] = get_session_id_from_visit(
            conn, data_collection_info.visit_string
        )
        params |= {
            k: v for k, v in asdict(data_collection_info).items() if k != "visit_string"
        }

        return params


def populate_remaining_data_collection_info(
    comment_constructor,
    data_collection_group_id,
    data_collection_info: DataCollectionInfo,
    detector_params,
    ispyb_params,
):
    get_visit_string(ispyb_params, detector_params)
    data_collection_info.parent_id = data_collection_group_id
    data_collection_info.sample_id = ispyb_params.sample_id
    data_collection_info.detector_id = I03_EIGER_DETECTOR
    data_collection_info.axis_start = data_collection_info.omega_start
    data_collection_info.focal_spot_size_at_samplex = ispyb_params.focal_spot_size_x
    data_collection_info.focal_spot_size_at_sampley = ispyb_params.focal_spot_size_y
    data_collection_info.slitgap_vertical = ispyb_params.slit_gap_size_y
    data_collection_info.slitgap_horizontal = ispyb_params.slit_gap_size_x
    data_collection_info.beamsize_at_samplex = ispyb_params.beam_size_x
    data_collection_info.beamsize_at_sampley = ispyb_params.beam_size_y
    # Ispyb wants the transmission in a percentage, we use fractions
    data_collection_info.transmission = ispyb_params.transmission_fraction * 100
    data_collection_info.comments = comment_constructor()
    data_collection_info.detector_distance = detector_params.detector_distance
    data_collection_info.exp_time = detector_params.exposure_time
    data_collection_info.imgdir = detector_params.directory
    data_collection_info.imgprefix = detector_params.prefix
    data_collection_info.imgsuffix = EIGER_FILE_SUFFIX
    # Both overlap and n_passes included for backwards compatibility,
    # planned to be removed later
    data_collection_info.n_passes = 1
    data_collection_info.overlap = 0
    data_collection_info.flux = ispyb_params.flux
    data_collection_info.start_image_number = 1
    data_collection_info.resolution = ispyb_params.resolution
    data_collection_info.wavelength = ispyb_params.wavelength_angstroms
    beam_position = detector_params.get_beam_position_mm(
        detector_params.detector_distance
    )
    data_collection_info.xbeam = beam_position[0]
    data_collection_info.ybeam = beam_position[1]
    data_collection_info.synchrotron_mode = ispyb_params.synchrotron_mode
    data_collection_info.undulator_gap1 = ispyb_params.undulator_gap
    data_collection_info.start_time = get_current_time_string()
    # temporary file template until nxs filewriting is integrated and we can use
    # that file name
    data_collection_info.file_template = f"{detector_params.prefix}_{data_collection_info.data_collection_number}_master.h5"
    return data_collection_info


def populate_data_collection_position_info(ispyb_params):
    dc_pos_info = DataCollectionPositionInfo(
        ispyb_params.position[0],
        ispyb_params.position[1],
        ispyb_params.position[2],
    )
    return dc_pos_info


def populate_data_collection_group(experiment_type, detector_params, ispyb_params):
    dcg_info = DataCollectionGroupInfo(
        visit_string=get_visit_string(ispyb_params, detector_params),
        experiment_type=experiment_type,
        sample_id=ispyb_params.sample_id,
        sample_barcode=ispyb_params.sample_barcode,
    )
    return dcg_info
