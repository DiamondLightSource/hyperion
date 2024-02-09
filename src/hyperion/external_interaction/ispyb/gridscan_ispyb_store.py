from __future__ import annotations

from typing import Any

import ispyb
from dodal.devices.oav import utils as oav_utils
from ispyb.connector.mysqlsp.main import ISPyBMySQLSPConnector as Connector
from ispyb.sp.mxacquisition import MXAcquisition
from numpy import ndarray

from hyperion.external_interaction.ispyb.ispyb_dataclass import (
    GridscanIspybParams,
    Orientation,
)
from hyperion.external_interaction.ispyb.ispyb_store import (
    IspybIds,
    StoreInIspyb,
)
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)


class StoreGridscanInIspyb(StoreInIspyb):
    def __init__(
        self,
        ispyb_config: str,
        experiment_type: str,
        parameters: GridscanInternalParameters,
    ) -> None:
        super().__init__(ispyb_config, experiment_type)
        self.full_params: GridscanInternalParameters = parameters
        self._ispyb_params: GridscanIspybParams = (
            parameters.hyperion_params.ispyb_params
        )
        self.upper_left: list[int] | ndarray = self._ispyb_params.upper_left
        self.y_steps: int = self.full_params.experiment_params.y_steps
        self.y_step_size: float = self.full_params.experiment_params.y_step_size
        self._omega_start = 0
        self._data_collection_ids: tuple[int, ...] | None = None
        self.grid_ids: tuple[int, ...] | None = None

    def begin_deposition(self) -> IspybIds:
        # fmt: off
        with ispyb.open(self.ISPYB_CONFIG_PATH) as conn:
            self._detector_params = self.full_params.hyperion_params.detector_params  # type: ignore
            self._run_number = self._detector_params.run_number  # pyright: ignore
            self._data_collection_group_id = self._store_data_collection_group_table(
                conn  # pyright: ignore
            )
            self._xtal_snapshots = self._ispyb_params.xtal_snapshots_omega_start or []
            self._data_collection_ids = (
                self._store_data_collection_table(conn, self._data_collection_group_id),  # pyright: ignore
            )
            return IspybIds(
                data_collection_group_id=self._data_collection_group_id,
                data_collection_ids=self._data_collection_ids,
            )
        # fmt: on

    def update_deposition(self):
        assert (
            self.full_params is not None
        ), "StoreGridscanInIspyb failed to get parameters."
        (
            self._data_collection_ids,
            self.grid_ids,
            self._data_collection_group_id,
        ) = self._store_grid_scan(self.full_params)
        return IspybIds(
            data_collection_ids=self._data_collection_ids,
            data_collection_group_id=self._data_collection_group_id,
            grid_ids=self.grid_ids,
        )

    def end_deposition(self, success: str, reason: str):
        assert (
            self._data_collection_ids is not None
        ), "Can't end ISPyB deposition, data_collection IDs are missing"
        for id in self._data_collection_ids:
            self._end_deposition(id, success, reason)

    def _store_grid_scan(self, full_params: GridscanInternalParameters):
        self.full_params = full_params
        self._ispyb_params = full_params.hyperion_params.ispyb_params
        self._run_number = (
            self._detector_params.run_number
        )  # type:ignore # the validator always makes this int
        self._omega_start = self._detector_params.omega_start
        self._xtal_snapshots = self._ispyb_params.xtal_snapshots_omega_start or []
        self.upper_left = [
            int(self._ispyb_params.upper_left[0]),
            int(self._ispyb_params.upper_left[1]),
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
        params["axis_end"] = self._omega_start
        params["n_images"] = self.full_params.experiment_params.x_steps * self.y_steps
        return params

    def _store_grid_info_table(
        self, conn: Connector, ispyb_data_collection_id: int
    ) -> int:
        assert self._ispyb_params is not None
        assert self.full_params is not None
        assert self.upper_left is not None

        mx_acquisition: MXAcquisition = conn.mx_acquisition
        params = mx_acquisition.get_dc_grid_params()
        params["parentid"] = ispyb_data_collection_id
        params["dxinmm"] = self.full_params.experiment_params.x_step_size
        params["dyinmm"] = self.y_step_size
        params["stepsx"] = self.full_params.experiment_params.x_steps
        params["stepsy"] = self.y_steps
        params["micronsPerPixelX"] = self._ispyb_params.microns_per_pixel_x
        params["micronsperpixely"] = self._ispyb_params.microns_per_pixel_y
        params["snapshotoffsetxpixel"], params["snapshotoffsetypixel"] = self.upper_left
        params["orientation"] = Orientation.HORIZONTAL.value
        params["snaked"] = True

        return mx_acquisition.upsert_dc_grid(list(params.values()))

    def _construct_comment(self) -> str:
        assert (
            self._ispyb_params is not None
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
            self._ispyb_params.microns_per_pixel_x,
            self._ispyb_params.microns_per_pixel_y,
        )
        return (
            "Hyperion: Xray centring - Diffraction grid scan of "
            f"{self.full_params.experiment_params.x_steps} by "
            f"{self.y_steps} images in "
            f"{(self.full_params.experiment_params.x_step_size * 1e3):.1f} um by "
            f"{(self.y_step_size * 1e3):.1f} um steps. "
            f"Top left (px): [{int(self.upper_left[0])},{int(self.upper_left[1])}], "
            f"bottom right (px): [{bottom_right[0]},{bottom_right[1]}]."
        )
