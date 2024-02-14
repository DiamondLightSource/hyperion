from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from typing import cast

import ispyb
from dodal.devices.oav import utils as oav_utils
from ispyb.connector.mysqlsp.main import ISPyBMySQLSPConnector as Connector
from ispyb.sp.mxacquisition import MXAcquisition
from numpy import ndarray

from hyperion.external_interaction.ispyb.ispyb_dataclass import (
    Orientation,
)
from hyperion.external_interaction.ispyb.ispyb_store import (
    DataCollectionInfo,
    IspybIds,
    StoreInIspyb,
)
from hyperion.parameters.internal_parameters import InternalParameters
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)


@dataclass
class GridScanInfo:
    upper_left: list[int] | ndarray
    y_steps: int
    y_step_size: float


class StoreGridscanInIspyb(StoreInIspyb):
    def __init__(self, ispyb_config: str) -> None:
        super().__init__(ispyb_config)
        self._data_collection_ids: tuple[int, ...] | None = None
        self.grid_ids: tuple[int, ...] | None = None

    def _get_xtal_snapshots(self, ispyb_params):
        return ispyb_params.xtal_snapshots_omega_start or []

    def begin_deposition(self, internal_params: InternalParameters) -> IspybIds:
        full_params = cast(GridscanInternalParameters, internal_params)
        ispyb_params = full_params.hyperion_params.ispyb_params
        detector_params = full_params.hyperion_params.detector_params
        # fmt: off
        with ispyb.open(self.ISPYB_CONFIG_PATH) as conn:
            assert conn is not None
            detector_params = full_params.hyperion_params.detector_params  # type: ignore
            self._data_collection_group_id = self._store_data_collection_group_table(conn, ispyb_params,
                                                                                     detector_params)

            grid_scan_info = GridScanInfo(
                ispyb_params.upper_left,
                full_params.experiment_params.y_steps,
                full_params.experiment_params.y_step_size,
            )

            def constructor():
                return self._construct_comment(full_params, ispyb_params, grid_scan_info)

            assert ispyb_params is not None and detector_params is not None
            data_collection_info = self._populate_xy_data_collection_info(grid_scan_info, full_params, ispyb_params,
                                                                          detector_params)
            params = self.fill_common_data_collection_params(constructor, conn, self._data_collection_group_id, None,
                                                             ispyb_params, detector_params, data_collection_info)
            self._data_collection_ids = (
                self._upsert_data_collection(conn, params),  # pyright: ignore
            )
            return IspybIds(
                data_collection_group_id=self._data_collection_group_id,
                data_collection_ids=self._data_collection_ids,
            )
        # fmt: on

    def update_deposition(self, internal_params):
        full_params = cast(GridscanInternalParameters, internal_params)
        assert full_params is not None, "StoreGridscanInIspyb failed to get parameters."
        ispyb_ids = self._store_grid_scan(
            full_params,
            full_params.hyperion_params.ispyb_params,
            full_params.hyperion_params.detector_params,
        )
        self._data_collection_ids = ispyb_ids.data_collection_ids  # pyright: ignore
        self._data_collection_group_id = ispyb_ids.data_collection_group_id
        self.grid_ids = ispyb_ids.grid_ids
        return ispyb_ids

    def end_deposition(self, success: str, reason: str, internal_params):
        full_params = cast(GridscanInternalParameters, internal_params)
        ispyb_params = full_params.hyperion_params.ispyb_params
        detector_params = full_params.hyperion_params.detector_params
        assert (
            self._data_collection_ids
        ), "Can't end ISPyB deposition, data_collection IDs are missing"
        for id in self._data_collection_ids:
            self._end_deposition(id, success, reason, ispyb_params, detector_params)

    def _store_grid_scan(
        self, full_params: GridscanInternalParameters, ispyb_params, detector_params
    ) -> IspybIds:
        grid_scan_info = GridScanInfo(
            [
                int(ispyb_params.upper_left[0]),
                int(ispyb_params.upper_left[1]),
            ],
            full_params.experiment_params.y_steps,
            full_params.experiment_params.y_step_size,
        )

        xy_data_collection_info = self._populate_xy_data_collection_info(
            grid_scan_info, full_params, ispyb_params, detector_params
        )

        with ispyb.open(self.ISPYB_CONFIG_PATH) as conn:
            assert conn is not None, "Failed to connect to ISPyB"
            return self._store_scan_data(
                conn,
                xy_data_collection_info,
                grid_scan_info,
                full_params,
                ispyb_params,
                detector_params,
            )

    def _populate_xy_data_collection_info(
        self, grid_scan_info: GridScanInfo, full_params, ispyb_params, detector_params
    ):
        info = DataCollectionInfo(
            detector_params.omega_start,
            detector_params.run_number,
            self._get_xtal_snapshots(ispyb_params),
            full_params.experiment_params.x_steps * grid_scan_info.y_steps,
            0,
            detector_params.omega_start,
        )
        return info

    @abstractmethod
    def _store_scan_data(
        self,
        conn: Connector,
        xy_data_collection_info: DataCollectionInfo,
        grid_scan_info: GridScanInfo,
        full_params,
        ispyb_params,
        detector_params,
    ) -> IspybIds:
        pass

    def _store_grid_info_table(
        self,
        conn: Connector,
        ispyb_data_collection_id: int,
        grid_scan_info,
        full_params,
        ispyb_params,
    ) -> int:
        assert ispyb_params is not None
        assert full_params is not None
        assert grid_scan_info.upper_left is not None

        mx_acquisition: MXAcquisition = conn.mx_acquisition
        params = mx_acquisition.get_dc_grid_params()
        params["parentid"] = ispyb_data_collection_id
        params["dxinmm"] = full_params.experiment_params.x_step_size
        params["dyinmm"] = grid_scan_info.y_step_size
        params["stepsx"] = full_params.experiment_params.x_steps
        params["stepsy"] = grid_scan_info.y_steps
        params["micronsPerPixelX"] = ispyb_params.microns_per_pixel_x
        params["micronsperpixely"] = ispyb_params.microns_per_pixel_y
        (
            params["snapshotoffsetxpixel"],
            params["snapshotoffsetypixel"],
        ) = grid_scan_info.upper_left
        params["orientation"] = Orientation.HORIZONTAL.value
        params["snaked"] = True

        return mx_acquisition.upsert_dc_grid(list(params.values()))

    def _construct_comment(self, full_params, ispyb_params, grid_scan_info) -> str:
        assert (
            ispyb_params is not None
            and full_params is not None
            and grid_scan_info is not None
        ), "StoreGridScanInIspyb failed to get parameters"

        bottom_right = oav_utils.bottom_right_from_top_left(
            grid_scan_info.upper_left,  # type: ignore
            full_params.experiment_params.x_steps,
            grid_scan_info.y_steps,
            full_params.experiment_params.x_step_size,
            grid_scan_info.y_step_size,
            ispyb_params.microns_per_pixel_x,
            ispyb_params.microns_per_pixel_y,
        )
        return (
            "Hyperion: Xray centring - Diffraction grid scan of "
            f"{full_params.experiment_params.x_steps} by "
            f"{grid_scan_info.y_steps} images in "
            f"{(full_params.experiment_params.x_step_size * 1e3):.1f} um by "
            f"{(grid_scan_info.y_step_size * 1e3):.1f} um steps. "
            f"Top left (px): [{int(grid_scan_info.upper_left[0])},{int(grid_scan_info.upper_left[1])}], "
            f"bottom right (px): [{bottom_right[0]},{bottom_right[1]}]."
        )
