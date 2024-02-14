from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Optional, cast

import ispyb
import ispyb.sqlalchemy
from dodal.devices.detector import DetectorParams
from ispyb.connector.mysqlsp.main import ISPyBMySQLSPConnector as Connector
from ispyb.sp.mxacquisition import MXAcquisition
from ispyb.strictordereddict import StrictOrderedDict
from pydantic import BaseModel

from hyperion.external_interaction.ispyb.ispyb_dataclass import (
    IspybParams,
)
from hyperion.external_interaction.ispyb.ispyb_utils import (
    get_current_time_string,
    get_session_id_from_visit,
    get_visit_string_from_path,
)
from hyperion.log import ISPYB_LOGGER
from hyperion.tracing import TRACER

if TYPE_CHECKING:
    pass

I03_EIGER_DETECTOR = 78
EIGER_FILE_SUFFIX = "h5"


class IspybIds(BaseModel):
    data_collection_ids: int | tuple[int, ...] | None = None
    data_collection_group_id: int | None = None
    grid_ids: tuple[int, ...] | None = None


class StoreInIspyb(ABC):
    def __init__(self, ispyb_config: str, experiment_type: str) -> None:
        self.ISPYB_CONFIG_PATH: str = ispyb_config
        self._experiment_type = experiment_type
        self._ispyb_params: IspybParams
        self._detector_params: DetectorParams
        self._run_number: int
        self._omega_start: float
        self._xtal_snapshots: list[str]
        self._data_collection_group_id: int | None

    @abstractmethod
    def _store_scan_data(self, conn: Connector) -> tuple:
        pass

    @abstractmethod
    def _construct_comment(self) -> str:
        pass

    @abstractmethod
    def _mutate_data_collection_params_for_experiment(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        pass

    @abstractmethod
    def begin_deposition(self) -> IspybIds:
        pass

    @abstractmethod
    def update_deposition(self) -> IspybIds:
        pass

    @abstractmethod
    def end_deposition(self, success: str, reason: str):
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

    def _get_visit_string(self) -> str:
        assert (
            self._ispyb_params and self._detector_params
        ), "StoreInISPyB didn't acquire params"
        visit_path_match = get_visit_string_from_path(self._ispyb_params.visit_path)
        if visit_path_match:
            return visit_path_match
        visit_path_match = get_visit_string_from_path(self._detector_params.directory)
        if not visit_path_match:
            raise ValueError(
                f"Visit not found from {self._ispyb_params.visit_path} or {self._detector_params.directory}"
            )
        return visit_path_match

    def _update_scan_with_end_time_and_status(
        self,
        end_time: str,
        run_status: str,
        reason: str,
        data_collection_id: int,
        data_collection_group_id: int,
    ) -> None:
        assert self._ispyb_params is not None and self._detector_params is not None
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
            current_time,
            run_status,
            reason,
            dcid,
            self._data_collection_group_id,
        )

    def _store_position_table(self, conn: Connector, dc_id: int) -> int:
        assert self._ispyb_params is not None
        mx_acquisition: MXAcquisition = conn.mx_acquisition
        params = mx_acquisition.get_dc_position_params()

        params["id"] = dc_id
        (
            params["pos_x"],
            params["pos_y"],
            params["pos_z"],
        ) = self._ispyb_params.position.tolist()

        return mx_acquisition.update_dc_position(list(params.values()))

    def _store_data_collection_group_table(
        self, conn: Connector, data_collection_group_id: Optional[int] = None
    ) -> int:
        assert self._ispyb_params is not None
        mx_acquisition: MXAcquisition = conn.mx_acquisition

        params = mx_acquisition.get_data_collection_group_params()
        if data_collection_group_id:
            params["id"] = data_collection_group_id

        params["parentid"] = get_session_id_from_visit(conn, self._get_visit_string())
        params["experimenttype"] = self._experiment_type
        params["sampleid"] = self._ispyb_params.sample_id
        params["sample_barcode"] = self._ispyb_params.sample_barcode

        return self._upsert_data_collection_group(conn, params)

    @staticmethod
    def _upsert_data_collection_group(
        conn: Connector, params: StrictOrderedDict
    ) -> int:
        return conn.mx_acquisition.upsert_data_collection_group(list(params.values()))

    @staticmethod
    def _upsert_data_collection(conn: Connector, params: StrictOrderedDict) -> int:
        return conn.mx_acquisition.upsert_data_collection(list(params.values()))

    @TRACER.start_as_current_span("store_ispyb_data_collection_table")
    def _store_data_collection_table(
        self,
        conn: Connector,
        data_collection_group_id: int,
        data_collection_id: Optional[int] = None,
    ) -> int:
        assert self._ispyb_params is not None and self._detector_params is not None

        mx_acquisition: MXAcquisition = conn.mx_acquisition

        params = mx_acquisition.get_data_collection_params()

        if data_collection_id:
            params["id"] = data_collection_id

        params["visitid"] = get_session_id_from_visit(conn, self._get_visit_string())
        params["parentid"] = data_collection_group_id
        params["sampleid"] = self._ispyb_params.sample_id
        params["detectorid"] = I03_EIGER_DETECTOR
        params["axis_start"] = self._omega_start
        params["focal_spot_size_at_samplex"] = self._ispyb_params.focal_spot_size_x
        params["focal_spot_size_at_sampley"] = self._ispyb_params.focal_spot_size_y
        params["slitgap_vertical"] = self._ispyb_params.slit_gap_size_y
        params["slitgap_horizontal"] = self._ispyb_params.slit_gap_size_x
        params["beamsize_at_samplex"] = self._ispyb_params.beam_size_x
        params["beamsize_at_sampley"] = self._ispyb_params.beam_size_y
        # Ispyb wants the transmission in a percentage, we use fractions
        params["transmission"] = self._ispyb_params.transmission_fraction * 100
        params["comments"] = self._construct_comment()
        params["data_collection_number"] = self._run_number
        params["detector_distance"] = self._detector_params.detector_distance
        params["exp_time"] = self._detector_params.exposure_time
        params["imgdir"] = self._detector_params.directory
        params["imgprefix"] = self._detector_params.prefix
        params["imgsuffix"] = EIGER_FILE_SUFFIX

        # Both overlap and n_passes included for backwards compatibility,
        # planned to be removed later
        params["n_passes"] = 1
        params["overlap"] = 0

        params["flux"] = self._ispyb_params.flux
        params["omegastart"] = self._omega_start
        params["start_image_number"] = 1
        params["resolution"] = self._ispyb_params.resolution
        params["wavelength"] = self._ispyb_params.wavelength_angstroms
        beam_position = self._detector_params.get_beam_position_mm(
            self._detector_params.detector_distance
        )
        params["xbeam"], params["ybeam"] = beam_position
        if self._xtal_snapshots and len(self._xtal_snapshots) == 3:
            (
                params["xtal_snapshot1"],
                params["xtal_snapshot2"],
                params["xtal_snapshot3"],
            ) = self._xtal_snapshots
        params["synchrotron_mode"] = self._ispyb_params.synchrotron_mode
        params["undulator_gap1"] = self._ispyb_params.undulator_gap
        params["starttime"] = get_current_time_string()

        # temporary file template until nxs filewriting is integrated and we can use
        # that file name
        params["file_template"] = (
            f"{self._detector_params.prefix}_{self._run_number}_master.h5"
        )

        params = cast(
            StrictOrderedDict,
            self._mutate_data_collection_params_for_experiment(params),
        )

        return self._upsert_data_collection(conn, params)
