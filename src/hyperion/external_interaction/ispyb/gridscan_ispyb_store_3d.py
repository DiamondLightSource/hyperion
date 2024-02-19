from __future__ import annotations

from itertools import zip_longest
from typing import Sequence

from ispyb.connector.mysqlsp.main import ISPyBMySQLSPConnector as Connector

from hyperion.external_interaction.ispyb.data_model import (
    DataCollectionInfo,
    GridScanInfo,
    ScanDataInfo,
)
from hyperion.external_interaction.ispyb.gridscan_ispyb_store import (
    StoreGridscanInIspyb,
)
from hyperion.external_interaction.ispyb.ispyb_store import (
    IspybIds,
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
        scan_data_infos: Sequence[ScanDataInfo],
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

        grid_ids = []
        data_collection_ids_out = []
        for scan_data_info, data_collection_id in zip_longest(
            scan_data_infos, data_collection_ids
        ):
            data_collection_id, grid_id = self._store_single_scan_data(
                conn,
                scan_data_info,
                data_collection_id,
            )
            data_collection_ids_out.append(data_collection_id)
            grid_ids.append(grid_id)

        return IspybIds(
            data_collection_ids=tuple(data_collection_ids_out),
            grid_ids=tuple(grid_ids),
            data_collection_group_id=data_collection_group_id,
        )


def populate_xz_data_collection_info(
    grid_scan_info: GridScanInfo,
    full_params,
    ispyb_params,
    detector_params,
) -> DataCollectionInfo:
    assert (
        detector_params.omega_start is not None
        and detector_params.run_number is not None
        and ispyb_params is not None
        and full_params is not None
    ), "StoreGridscanInIspyb failed to get parameters"
    omega_start = detector_params.omega_start + 90
    run_number = detector_params.run_number + 1
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
