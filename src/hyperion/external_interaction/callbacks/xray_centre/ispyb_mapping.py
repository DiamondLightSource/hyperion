from __future__ import annotations

from dodal.devices.oav import utils as oav_utils

from hyperion.external_interaction.ispyb.data_model import (
    DataCollectionGridInfo,
    DataCollectionInfo,
    GridScanInfo,
)
from hyperion.external_interaction.ispyb.ispyb_dataclass import Orientation


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


def populate_xy_data_collection_info(
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


def construct_comment_for_gridscan(full_params, ispyb_params, grid_scan_info) -> str:
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
