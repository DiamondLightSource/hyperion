from __future__ import annotations

import datetime
import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import dodal.devices.oav.utils as oav_utils
import ispyb
import ispyb.sqlalchemy
from dodal.devices.detector import DetectorParams
from ispyb.connector.mysqlsp.main import ISPyBMySQLSPConnector as Connector
from ispyb.sp.core import Core
from ispyb.sp.mxacquisition import MXAcquisition
from numpy import ndarray
from pydantic import BaseModel

from hyperion.external_interaction.ispyb.ispyb_dataclass import (
    GridscanIspybParams,
    IspybParams,
    Orientation,
    RotationIspybParams,
)
from hyperion.log import LOGGER
from hyperion.tracing import TRACER

if TYPE_CHECKING:
    from hyperion.parameters.plan_specific.gridscan_internal_params import (
        GridscanInternalParameters,
    )
    from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
        RotationInternalParameters,
    )

I03_EIGER_DETECTOR = 78
EIGER_FILE_SUFFIX = "h5"
VISIT_PATH_REGEX = r".+/([a-zA-Z]{2}\d{4,5}-\d{1,3})(/?$)"


class IspybIds(BaseModel):
    data_collection_ids: int | tuple[int, ...] | None = None
    data_collection_group_id: int | None = None
    grid_ids: tuple[int, ...] | None = None


class StoreInIspyb(ABC):
    def __init__(self, ispyb_config: str, experiment_type: str) -> None:
        self.ISPYB_CONFIG_PATH: str = ispyb_config
        self.experiment_type = experiment_type
        self.ispyb_params: IspybParams
        self.detector_params: DetectorParams
        self.run_number: int
        self.omega_start: float
        self.experiment_type: str
        self.xtal_snapshots: list[str]
        self.data_collection_group_id: int

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

    def get_current_time_string(self):
        now = datetime.datetime.now()
        return now.strftime("%Y-%m-%d %H:%M:%S")

    def get_visit_string(self):
        assert (
            self.ispyb_params and self.detector_params
        ), "StoreInISPyB didn't acquire params"
        visit_path_match = self.get_visit_string_from_path(self.ispyb_params.visit_path)
        if visit_path_match:
            return visit_path_match
        else:
            return self.get_visit_string_from_path(self.detector_params.directory)

    def get_visit_string_from_path(self, path):
        match = re.search(VISIT_PATH_REGEX, path) if path else None
        return match.group(1) if match else None

    def update_scan_with_end_time_and_status(
        self,
        end_time: str,
        run_status: str,
        reason: str,
        data_collection_id: int,
        data_collection_group_id: int,
    ) -> None:
        assert self.ispyb_params is not None and self.detector_params is not None
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
        LOGGER.info(
            f"End ispyb deposition with status '{success}' and reason '{reason}'."
        )
        if success == "fail" or success == "abort":
            run_status = "DataCollection Unsuccessful"
        else:
            run_status = "DataCollection Successful"
        current_time = self.get_current_time_string()
        assert self.data_collection_group_id is not None
        self.update_scan_with_end_time_and_status(
            current_time,
            run_status,
            reason,
            dcid,
            self.data_collection_group_id,
        )

    def _store_position_table(self, conn: Connector, dc_id: int) -> int:
        assert self.ispyb_params is not None
        mx_acquisition: MXAcquisition = conn.mx_acquisition
        params = mx_acquisition.get_dc_position_params()

        params["id"] = dc_id
        (
            params["pos_x"],
            params["pos_y"],
            params["pos_z"],
        ) = self.ispyb_params.position.tolist()

        return mx_acquisition.update_dc_position(list(params.values()))

    def _store_data_collection_group_table(self, conn: Connector) -> int:
        assert self.ispyb_params is not None
        core: Core = conn.core
        mx_acquisition: MXAcquisition = conn.mx_acquisition

        try:
            session_id = core.retrieve_visit_id(self.get_visit_string())
        except ispyb.NoResult:
            raise Exception(
                f"Not found - session ID for visit {self.get_visit_string()} where self.ispyb_params.visit_path is {self.ispyb_params.visit_path}"
            )

        params = mx_acquisition.get_data_collection_group_params()
        params["parentid"] = session_id
        params["experimenttype"] = self.experiment_type
        params["sampleid"] = self.ispyb_params.sample_id
        params["sample_barcode"] = self.ispyb_params.sample_barcode

        return mx_acquisition.upsert_data_collection_group(list(params.values()))

    @TRACER.start_as_current_span("store_ispyb_data_collection_table")
    def _store_data_collection_table(
        self, conn: Connector, data_collection_group_id: int
    ) -> int:
        assert (
            self.ispyb_params is not None
            and self.detector_params is not None
            and self.xtal_snapshots is not None
        )

        core: Core = conn.core
        mx_acquisition: MXAcquisition = conn.mx_acquisition
        try:
            session_id = core.retrieve_visit_id(self.get_visit_string())
        except ispyb.NoResult:
            raise Exception(
                f"Not found - session ID for visit {self.get_visit_string()}"
            )

        params = mx_acquisition.get_data_collection_params()

        params["visitid"] = session_id
        params["parentid"] = data_collection_group_id
        params["sampleid"] = self.ispyb_params.sample_id
        params["detectorid"] = I03_EIGER_DETECTOR
        params["axis_start"] = self.omega_start
        params["focal_spot_size_at_samplex"] = self.ispyb_params.focal_spot_size_x
        params["focal_spot_size_at_sampley"] = self.ispyb_params.focal_spot_size_y
        params["slitgap_vertical"] = self.ispyb_params.slit_gap_size_y
        params["slitgap_horizontal"] = self.ispyb_params.slit_gap_size_x
        params["beamsize_at_samplex"] = self.ispyb_params.beam_size_x
        params["beamsize_at_sampley"] = self.ispyb_params.beam_size_y
        # Ispyb wants the transmission in a percentage, we use fractions
        params["transmission"] = self.ispyb_params.transmission_fraction * 100
        params["comments"] = self._construct_comment()
        params["data_collection_number"] = self.run_number
        params["detector_distance"] = self.detector_params.detector_distance
        params["exp_time"] = self.detector_params.exposure_time
        params["imgdir"] = self.detector_params.directory
        params["imgprefix"] = self.detector_params.prefix
        params["imgsuffix"] = EIGER_FILE_SUFFIX

        # Both overlap and n_passes included for backwards compatibility,
        # planned to be removed later
        params["n_passes"] = 1
        params["overlap"] = 0

        params["flux"] = self.ispyb_params.flux
        params["omegastart"] = self.omega_start
        params["start_image_number"] = 1
        params["resolution"] = self.ispyb_params.resolution
        params["wavelength"] = self.ispyb_params.wavelength_angstroms
        beam_position = self.detector_params.get_beam_position_mm(
            self.detector_params.detector_distance
        )
        params["xbeam"], params["ybeam"] = beam_position
        if len(self.xtal_snapshots) == 3:
            (
                params["xtal_snapshot1"],
                params["xtal_snapshot2"],
                params["xtal_snapshot3"],
            ) = self.xtal_snapshots
        params["synchrotron_mode"] = self.ispyb_params.synchrotron_mode
        params["undulator_gap1"] = self.ispyb_params.undulator_gap
        params["starttime"] = self.get_current_time_string()

        # temporary file template until nxs filewriting is integrated and we can use
        # that file name
        params[
            "file_template"
        ] = f"{self.detector_params.prefix}_{self.run_number}_master.h5"

        params = self._mutate_data_collection_params_for_experiment(params)

        return mx_acquisition.upsert_data_collection(list(params.values()))


class StoreRotationInIspyb(StoreInIspyb):
    def __init__(self, ispyb_config, parameters: RotationInternalParameters) -> None:
        super().__init__(ispyb_config, "SAD")
        self.full_params: RotationInternalParameters = parameters
        self.ispyb_params: RotationIspybParams = parameters.hyperion_params.ispyb_params
        self.detector_params = parameters.hyperion_params.detector_params
        self.run_number = self.detector_params.run_number
        self.omega_start = self.detector_params.omega_start
        self.data_collection_id: int | None = None

        if self.ispyb_params.xtal_snapshots_omega_start:
            self.xtal_snapshots = self.ispyb_params.xtal_snapshots_omega_start[:3]
            LOGGER.info(
                f"Using rotation scan snapshots {self.xtal_snapshots} for ISPyB deposition"
            )
        else:
            self.xtal_snapshots = []
            LOGGER.warning("No xtal snapshot paths sent to ISPyB!")

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
        data_collection_group_id = self._store_data_collection_group_table(conn)
        self.data_collection_group_id = data_collection_group_id
        data_collection_id = self._store_data_collection_table(
            conn, data_collection_group_id
        )
        self.data_collection_id = data_collection_id
        self._store_position_table(conn, data_collection_id)

        return data_collection_id, data_collection_group_id

    def begin_deposition(self) -> IspybIds:
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


class StoreGridscanInIspyb(StoreInIspyb):
    def __init__(
        self,
        ispyb_config: str,
        experiment_type: str,
        parameters: GridscanInternalParameters,
    ) -> None:
        super().__init__(ispyb_config, experiment_type)
        self.full_params: GridscanInternalParameters = parameters
        self.ispyb_params: GridscanIspybParams = parameters.hyperion_params.ispyb_params
        self.upper_left: list[int] | ndarray = self.ispyb_params.upper_left
        self.y_steps: int = self.full_params.experiment_params.y_steps
        self.y_step_size: float = self.full_params.experiment_params.y_step_size
        self.omega_start = 0
        self.data_collection_ids: tuple[int, ...] | None = None
        self.grid_ids: tuple[int, ...] | None = None

    def begin_deposition(self):
        assert (
            self.full_params is not None
        ), "StoreGridscanInIspyb failed to get parameters."
        (
            self.data_collection_ids,
            self.grid_ids,
            self.data_collection_group_id,
        ) = self.store_grid_scan(self.full_params)
        return IspybIds(
            data_collection_ids=self.data_collection_ids,
            data_collection_group_id=self.data_collection_group_id,
            grid_ids=self.grid_ids,
        )

    def end_deposition(self, success: str, reason: str):
        assert (
            self.data_collection_ids is not None
        ), "Can't end ISPyB deposition, data_collection IDs are missing"
        for id in self.data_collection_ids:
            self._end_deposition(id, success, reason)

    def store_grid_scan(self, full_params: GridscanInternalParameters):
        self.full_params = full_params
        self.ispyb_params = full_params.hyperion_params.ispyb_params
        self.detector_params = full_params.hyperion_params.detector_params
        self.run_number = self.detector_params.run_number
        self.omega_start = self.detector_params.omega_start
        self.xtal_snapshots = self.ispyb_params.xtal_snapshots_omega_start or []
        self.upper_left = [
            int(self.ispyb_params.upper_left[0]),
            int(self.ispyb_params.upper_left[1]),
        ]
        self.y_steps = full_params.experiment_params.y_steps
        self.y_step_size = full_params.experiment_params.y_step_size

        with ispyb.open(self.ISPYB_CONFIG_PATH) as conn:
            assert conn is not None, "Failed to connect to ISPyB"
            return self._store_scan_data(conn)

    def _mutate_data_collection_params_for_experiment(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        assert self.full_params and self.y_steps
        params["axis_range"] = 0
        params["axis_end"] = self.omega_start
        params["n_images"] = self.full_params.experiment_params.x_steps * self.y_steps
        return params

    def _store_grid_info_table(
        self, conn: Connector, ispyb_data_collection_id: int
    ) -> int:
        assert self.ispyb_params is not None
        assert self.full_params is not None
        assert self.upper_left is not None

        mx_acquisition: MXAcquisition = conn.mx_acquisition
        params = mx_acquisition.get_dc_grid_params()

        params["parentid"] = ispyb_data_collection_id
        params["dxInMm"] = self.full_params.experiment_params.x_step_size
        params["dyInMm"] = self.y_step_size
        params["stepsX"] = self.full_params.experiment_params.x_steps
        params["stepsY"] = self.y_steps
        # Although the stored values is microns per pixel the columns in ISPyB are named
        # pixels per micron. See LIMS-564, which is tasked with fixing this inconsistency
        params["pixelsPerMicronX"] = self.ispyb_params.microns_per_pixel_x
        params["pixelsPerMicronY"] = self.ispyb_params.microns_per_pixel_y
        params["snapshotOffsetXPixel"], params["snapshotOffsetYPixel"] = self.upper_left
        params["orientation"] = Orientation.HORIZONTAL.value
        params["snaked"] = True

        return mx_acquisition.upsert_dc_grid(list(params.values()))

    def _construct_comment(self) -> str:
        assert (
            self.ispyb_params is not None
            and self.full_params is not None
            and self.upper_left is not None
            and self.y_step_size is not None
            and self.y_steps is not None
        ), "StoreGridScanInIspyb failed to get parameters"

        bottom_right = oav_utils.bottom_right_from_top_left(
            self.upper_left,  # type: ignore
            self.full_params.experiment_params.x_steps,
            self.y_steps,
            self.full_params.experiment_params.x_step_size,
            self.y_step_size,
            self.ispyb_params.microns_per_pixel_x,
            self.ispyb_params.microns_per_pixel_y,
        )
        return (
            "Hyperion: Xray centring - Diffraction grid scan of "
            f"{self.full_params.experiment_params.x_steps} by "
            f"{self.y_steps} images in "
            f"{self.full_params.experiment_params.x_step_size*1e3} um by "
            f"{self.y_step_size*1e3} um steps. "
            f"Top left (px): [{int(self.upper_left[0])},{int(self.upper_left[1])}], "
            f"bottom right (px): [{bottom_right[0]},{bottom_right[1]}]."
        )


class Store3DGridscanInIspyb(StoreGridscanInIspyb):
    def __init__(self, ispyb_config: str, parameters: GridscanInternalParameters):
        super().__init__(ispyb_config, "Mesh3D", parameters)

    def _store_scan_data(self, conn: Connector):
        data_collection_group_id = self._store_data_collection_group_table(conn)

        data_collection_id_1 = self._store_data_collection_table(
            conn, data_collection_group_id
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


class Store2DGridscanInIspyb(StoreGridscanInIspyb):
    def __init__(self, ispyb_config: str, parameters: GridscanInternalParameters):
        super().__init__(ispyb_config, "mesh", parameters)

    def _store_scan_data(self, conn: Connector):
        data_collection_group_id = self._store_data_collection_group_table(conn)

        data_collection_id = self._store_data_collection_table(
            conn, data_collection_group_id
        )

        self._store_position_table(conn, data_collection_id)

        grid_id = self._store_grid_info_table(conn, data_collection_id)

        return [data_collection_id], [grid_id], data_collection_group_id
