from __future__ import annotations

from dodal.devices.oav import utils as oav_utils

from hyperion.external_interaction.callbacks.common.ispyb_mapping import GridScanInfo
from hyperion.external_interaction.ispyb.data_model import (
    DataCollectionGridInfo,
    DataCollectionInfo,
)
from hyperion.external_interaction.ispyb.ispyb_dataclass import Orientation
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)


def populate_data_collection_info(grid_scan_info: GridScanInfo):
    info = DataCollectionInfo(
        omega_start=grid_scan_info.omega,
        data_collection_number=grid_scan_info.run_number,
        n_images=grid_scan_info.x_steps * grid_scan_info.y_steps,
        axis_range=0,
        axis_end=grid_scan_info.omega,
    )
    snapshots = grid_scan_info.crystal_snapshots or []
    info.xtal_snapshot1, info.xtal_snapshot2, info.xtal_snapshot3 = snapshots + [
        None
    ] * (3 - len(snapshots))
    return info


def construct_comment_for_gridscan(grid_scan_info: GridScanInfo) -> str:
    bottom_right = oav_utils.bottom_right_from_top_left(
        grid_scan_info.upper_left,  # type: ignore
        grid_scan_info.x_steps,
        grid_scan_info.y_steps,
        grid_scan_info.x_step_size,
        grid_scan_info.y_step_size,
        grid_scan_info.microns_per_pixel_x,
        grid_scan_info.microns_per_pixel_y,
    )
    return (
        "Hyperion: Xray centring - Diffraction grid scan of "
        f"{grid_scan_info.x_steps} by "
        f"{grid_scan_info.y_steps} images in "
        f"{(grid_scan_info.x_step_size * 1e3):.1f} um by "
        f"{(grid_scan_info.y_step_size * 1e3):.1f} um steps. "
        f"Top left (px): [{int(grid_scan_info.upper_left[0])},{int(grid_scan_info.upper_left[1])}], "
        f"bottom right (px): [{bottom_right[0]},{bottom_right[1]}]."
    )


def populate_data_collection_grid_info(grid_scan_info: GridScanInfo):
    dc_grid_info = DataCollectionGridInfo(
        dx_in_mm=grid_scan_info.x_step_size,
        dy_in_mm=grid_scan_info.y_step_size,
        steps_x=grid_scan_info.x_steps,
        steps_y=grid_scan_info.y_steps,
        microns_per_pixel_x=grid_scan_info.microns_per_pixel_x,
        snapshot_offset_x_pixel=grid_scan_info.upper_left[0],
        snapshot_offset_y_pixel=grid_scan_info.upper_left[1],
        microns_per_pixel_y=grid_scan_info.microns_per_pixel_y,
        orientation=Orientation.HORIZONTAL,
        snaked=True,
    )
    return dc_grid_info


def grid_scan_xy_from_internal_params(
    params: GridscanInternalParameters,
) -> GridScanInfo:
    return GridScanInfo(
        [
            int(params.hyperion_params.ispyb_params.upper_left[0]),
            int(params.hyperion_params.ispyb_params.upper_left[1]),
        ],
        params.experiment_params.y_steps,
        params.experiment_params.y_step_size,
        params.hyperion_params.ispyb_params.microns_per_pixel_y,
        params.experiment_params.x_steps,
        params.experiment_params.x_step_size,
        params.hyperion_params.ispyb_params.microns_per_pixel_x,
        params.hyperion_params.ispyb_params.xtal_snapshots_omega_start or [],
        params.hyperion_params.detector_params.omega_start,
        params.hyperion_params.detector_params.run_number,  # type:ignore
    )


def grid_scan_xz_from_internal_params(
    params: GridscanInternalParameters,
) -> GridScanInfo:
    return GridScanInfo(
        [
            int(params.hyperion_params.ispyb_params.upper_left[0]),
            int(params.hyperion_params.ispyb_params.upper_left[2]),
        ],
        params.experiment_params.z_steps,
        params.experiment_params.z_step_size,
        params.hyperion_params.ispyb_params.microns_per_pixel_y,
        params.experiment_params.x_steps,
        params.experiment_params.x_step_size,
        params.hyperion_params.ispyb_params.microns_per_pixel_x,
        params.hyperion_params.ispyb_params.xtal_snapshots_omega_end or [],
        params.hyperion_params.detector_params.omega_start + 90,
        params.hyperion_params.detector_params.run_number + 1,  # type:ignore
    )
