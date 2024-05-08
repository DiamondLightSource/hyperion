from __future__ import annotations

import numpy
from dodal.devices.detector import DetectorParams
from dodal.devices.oav import utils as oav_utils

from hyperion.external_interaction.ispyb.data_model import (
    DataCollectionGridInfo,
    DataCollectionInfo,
)


def populate_xz_data_collection_info(
    detector_params: DetectorParams,
) -> DataCollectionInfo:
    assert (
        detector_params.omega_start is not None
        and detector_params.run_number is not None
    ), "StoreGridscanInIspyb failed to get parameters"
    omega_start = detector_params.omega_start + 90
    run_number = detector_params.run_number + 1
    info = DataCollectionInfo(
        omega_start=omega_start,
        data_collection_number=run_number,
        axis_range=0,
        axis_end=omega_start,
    )
    return info


def populate_xy_data_collection_info(detector_params: DetectorParams):
    info = DataCollectionInfo(
        omega_start=detector_params.omega_start,
        data_collection_number=detector_params.run_number,
        axis_range=0,
        axis_end=detector_params.omega_start,
    )
    return info


def construct_comment_for_gridscan(grid_info: DataCollectionGridInfo) -> str:
    assert grid_info is not None, "StoreGridScanInIspyb failed to get parameters"

    bottom_right = oav_utils.bottom_right_from_top_left(
        numpy.array(
            [grid_info.snapshot_offset_x_pixel, grid_info.snapshot_offset_y_pixel]
        ),  # type: ignore
        grid_info.steps_x,
        grid_info.steps_y,
        grid_info.dx_in_mm,
        grid_info.dy_in_mm,
        grid_info.microns_per_pixel_x,
        grid_info.microns_per_pixel_y,
    )
    return (
        "Hyperion: Xray centring - Diffraction grid scan of "
        f"{grid_info.steps_x} by "
        f"{grid_info.steps_y} images in "
        f"{(grid_info.dx_in_mm * 1e3):.1f} um by "
        f"{(grid_info.dy_in_mm * 1e3):.1f} um steps. "
        f"Top left (px): [{int(grid_info.snapshot_offset_x_pixel)},{int(grid_info.snapshot_offset_y_pixel)}], "
        f"bottom right (px): [{bottom_right[0]},{bottom_right[1]}]."
    )
