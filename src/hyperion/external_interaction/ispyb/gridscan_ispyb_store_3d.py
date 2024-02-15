from __future__ import annotations

from ispyb.connector.mysqlsp.main import ISPyBMySQLSPConnector as Connector

from hyperion.external_interaction.ispyb.data_model import (
    DataCollectionInfo,
    GridScanInfo,
    ScanDataInfo,
)
from hyperion.external_interaction.ispyb.gridscan_ispyb_store import (
    StoreGridscanInIspyb,
    _construct_comment_for_gridscan,
    populate_data_collection_grid_info,
)
from hyperion.external_interaction.ispyb.ispyb_store import (
    IspybIds,
    populate_data_collection_position_info,
    populate_remaining_data_collection_info,
)


class Store3DGridscanInIspyb(StoreGridscanInIspyb):
    def __init__(self, ispyb_config: str):
        super().__init__(ispyb_config)

    @property
    def experiment_type(self):
        return "Mesh3D"

    def _store_scan_data(
        self,
        conn: Connector,
        xy_data_collection_info: DataCollectionInfo,
        xy_grid_scan_info: GridScanInfo,
        full_params,
        ispyb_params,
        detector_params,
        data_collection_group_id,
        data_collection_ids,
    ) -> IspybIds:
        assert (
            data_collection_group_id
        ), "Attempted to store scan data without a collection group"
        assert (
            data_collection_ids
        ), "Attempted to store scan data without at least one collection"
        assert ispyb_params is not None and detector_params is not None

        def xy_comment_constructor():
            return _construct_comment_for_gridscan(
                full_params, ispyb_params, xy_grid_scan_info
            )

        xy_data_collection_info = populate_remaining_data_collection_info(
            xy_comment_constructor,
            conn,
            data_collection_group_id,
            xy_data_collection_info,
            detector_params,
            ispyb_params,
        )
        xy_scan_data_info = ScanDataInfo(
            data_collection_info=xy_data_collection_info,
            data_collection_position_info=populate_data_collection_position_info(
                ispyb_params
            ),
            data_collection_grid_info=populate_data_collection_grid_info(
                full_params, xy_grid_scan_info, ispyb_params
            ),
        )

        xz_grid_scan_info = GridScanInfo(
            [
                int(ispyb_params.upper_left[0]),
                int(ispyb_params.upper_left[2]),
            ],
            full_params.experiment_params.z_steps,
            full_params.experiment_params.z_step_size,
        )
        xz_data_collection_info = _populate_xz_data_collection_info(
            xy_data_collection_info, xz_grid_scan_info, full_params, ispyb_params
        )

        def xz_comment_constructor():
            return _construct_comment_for_gridscan(
                full_params, ispyb_params, xz_grid_scan_info
            )

        xz_data_collection_info = populate_remaining_data_collection_info(
            xz_comment_constructor,
            conn,
            data_collection_group_id,
            xz_data_collection_info,
            detector_params,
            ispyb_params,
        )
        xz_scan_data_info = ScanDataInfo(
            data_collection_info=xz_data_collection_info,
            data_collection_grid_info=populate_data_collection_grid_info(
                full_params, xz_grid_scan_info, ispyb_params
            ),
            data_collection_position_info=populate_data_collection_position_info(
                ispyb_params
            ),
        )

        data_collection_id_1, grid_id_1 = self._store_single_scan_data(
            conn,
            xy_scan_data_info,
            data_collection_ids[0] if data_collection_ids else None,
        )

        data_collection_id_2, grid_id_2 = self._store_single_scan_data(
            conn, xz_scan_data_info
        )

        return IspybIds(
            data_collection_ids=(data_collection_id_1, data_collection_id_2),
            grid_ids=(grid_id_1, grid_id_2),
            data_collection_group_id=data_collection_group_id,
        )


def _populate_xz_data_collection_info(
    xy_data_collection_info: DataCollectionInfo,
    grid_scan_info: GridScanInfo,
    full_params,
    ispyb_params,
) -> DataCollectionInfo:
    assert (
        xy_data_collection_info.omega_start is not None
        and xy_data_collection_info.data_collection_number is not None
        and ispyb_params is not None
        and full_params is not None
    ), "StoreGridscanInIspyb failed to get parameters"
    omega_start = xy_data_collection_info.omega_start + 90
    run_number = xy_data_collection_info.data_collection_number + 1
    xtal_snapshots = ispyb_params.xtal_snapshots_omega_end or []
    info = DataCollectionInfo(
        omega_start=omega_start,
        data_collection_number=run_number,
        n_images=full_params.experiment_params.x_steps * grid_scan_info.y_steps,
        axis_range=0,
        axis_end=omega_start,
    )
    info.xtal_snapshot1, info.xtal_snapshot2, info.xtal_snapshot3 = xtal_snapshots + [
        None
    ] * (3 - len(xtal_snapshots))
    return info
