from __future__ import annotations

from abc import abstractmethod
from typing import cast

import ispyb
from dodal.devices.oav import utils as oav_utils
from ispyb.connector.mysqlsp.main import ISPyBMySQLSPConnector as Connector

from hyperion.external_interaction.ispyb.data_model import (
    DataCollectionGridInfo,
    DataCollectionGroupInfo,
    DataCollectionInfo,
    GridScanInfo,
    ScanDataInfo,
)
from hyperion.external_interaction.ispyb.ispyb_dataclass import (
    Orientation,
)
from hyperion.external_interaction.ispyb.ispyb_store import (
    IspybIds,
    StoreInIspyb,
    populate_data_collection_group,
    populate_remaining_data_collection_info,
)
from hyperion.parameters.internal_parameters import InternalParameters
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)


def populate_data_collection_grid_info(full_params, grid_scan_info, ispyb_params):
    assert ispyb_params is not None
    assert full_params is not None
    dc_grid_info = DataCollectionGridInfo(
        dx_in_mm=full_params.experiment_params.x_step_size,
        dy_in_mm=grid_scan_info.y_step_size,
        steps_x=full_params.experiment_params.x_steps,
        steps_y=grid_scan_info.y_steps,
        microns_per_pixel_x=ispyb_params.microns_per_pixel_x,
        snapshot_offset_x_pixel=grid_scan_info.upper_left[0],
        snapshot_offset_y_pixel=grid_scan_info.upper_left[1],
        microns_per_pixel_y=ispyb_params.microns_per_pixel_y,
        orientation=Orientation.HORIZONTAL,
        snaked=True,
    )
    return dc_grid_info


class StoreGridscanInIspyb(StoreInIspyb):
    def __init__(self, ispyb_config: str) -> None:
        super().__init__(ispyb_config)
        self._data_collection_ids: tuple[int, ...] | None = None
        self.grid_ids: tuple[int, ...] | None = None

    def begin_deposition(
        self,
        internal_params: InternalParameters,
        data_collection_group_info: DataCollectionGroupInfo = None,
        scan_data_info: ScanDataInfo = None,
    ) -> IspybIds:
        full_params = cast(GridscanInternalParameters, internal_params)
        ispyb_params = full_params.hyperion_params.ispyb_params
        detector_params = full_params.hyperion_params.detector_params
        assert ispyb_params is not None
        assert detector_params is not None
        # fmt: off
        with ispyb.open(self.ISPYB_CONFIG_PATH) as conn:
            assert conn is not None
            detector_params = full_params.hyperion_params.detector_params  # type: ignore
            dcg_info = populate_data_collection_group(self.experiment_type, detector_params, ispyb_params)
            self._data_collection_group_id = self._store_data_collection_group_table(conn, dcg_info)

            grid_scan_info = GridScanInfo(
                ispyb_params.upper_left,
                full_params.experiment_params.y_steps,
                full_params.experiment_params.y_step_size,
            )

            def constructor():
                return _construct_comment_for_gridscan(full_params, ispyb_params, grid_scan_info)

            assert ispyb_params is not None and detector_params is not None
            data_collection_info = _populate_xy_data_collection_info(grid_scan_info, full_params, ispyb_params,
                                                                     detector_params)
            populate_remaining_data_collection_info(constructor, self._data_collection_group_id, data_collection_info,
                                                    detector_params, ispyb_params)
            params = self.fill_common_data_collection_params(conn, None, data_collection_info)
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
            self._data_collection_group_id,
            self._data_collection_ids,
        )
        self._data_collection_ids = ispyb_ids.data_collection_ids  # pyright: ignore
        self._data_collection_group_id = ispyb_ids.data_collection_group_id
        self.grid_ids = ispyb_ids.grid_ids
        return ispyb_ids

    def end_deposition(self, success: str, reason: str, internal_params):
        assert (
            self._data_collection_ids
        ), "Can't end ISPyB deposition, data_collection IDs are missing"
        for id in self._data_collection_ids:
            self._end_deposition(id, success, reason)

    def _store_grid_scan(
        self,
        full_params: GridscanInternalParameters,
        ispyb_params,
        detector_params,
        data_collection_group_id,
        data_collection_ids,
    ) -> IspybIds:
        assert ispyb_params.upper_left is not None
        grid_scan_info = GridScanInfo(
            [
                int(ispyb_params.upper_left[0]),
                int(ispyb_params.upper_left[1]),
            ],
            full_params.experiment_params.y_steps,
            full_params.experiment_params.y_step_size,
        )

        xy_data_collection_info = _populate_xy_data_collection_info(
            grid_scan_info, full_params, ispyb_params, detector_params
        )

        with ispyb.open(self.ISPYB_CONFIG_PATH) as conn:
            assert conn is not None, "Failed to connect to ISPyB"
            dcg_info = populate_data_collection_group(
                self.experiment_type, detector_params, ispyb_params
            )

            self._store_data_collection_group_table(
                conn, dcg_info, data_collection_group_id
            )

            return self._store_scan_data(
                conn,
                xy_data_collection_info,
                grid_scan_info,
                full_params,
                ispyb_params,
                detector_params,
                data_collection_group_id,
                data_collection_ids,
            )

    @abstractmethod
    def _store_scan_data(
        self,
        conn: Connector,
        xy_data_collection_info: DataCollectionInfo,
        grid_scan_info: GridScanInfo,
        full_params,
        ispyb_params,
        detector_params,
        data_collection_group_id,
        data_collection_ids,
    ) -> IspybIds:
        pass


def _construct_comment_for_gridscan(full_params, ispyb_params, grid_scan_info) -> str:
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


def _populate_xy_data_collection_info(
    grid_scan_info: GridScanInfo, full_params, ispyb_params, detector_params
):
    info = DataCollectionInfo(
        omega_start=detector_params.omega_start,
        data_collection_number=detector_params.run_number,
        n_images=full_params.experiment_params.x_steps * grid_scan_info.y_steps,
        axis_range=0,
        axis_end=detector_params.omega_start,
    )
    snapshots = ispyb_params.xtal_snapshots_omega_start or []
    info.xtal_snapshot1, info.xtal_snapshot2, info.xtal_snapshot3 = snapshots + [
        None
    ] * (3 - len(snapshots))
    return info
