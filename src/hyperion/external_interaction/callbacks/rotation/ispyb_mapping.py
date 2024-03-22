from __future__ import annotations

from hyperion.external_interaction.callbacks.common.ispyb_mapping import (
    get_xtal_snapshots,
)
from hyperion.external_interaction.ispyb.data_model import DataCollectionInfo


def populate_data_collection_info_for_rotation(
    ispyb_params, detector_params, full_params
):
    info = DataCollectionInfo(
        omega_start=detector_params.omega_start,
        data_collection_number=detector_params.run_number,  # type:ignore # the validator always makes this int
        n_images=full_params.experiment_params.get_num_images(),
        axis_range=full_params.experiment_params.image_width,
        axis_end=(
            full_params.experiment_params.omega_start
            + full_params.experiment_params.rotation_angle
        ),
        kappa_start=full_params.experiment_params.chi_start,
    )
    (
        info.xtal_snapshot1,
        info.xtal_snapshot2,
        info.xtal_snapshot3,
    ) = get_xtal_snapshots(ispyb_params)
    return info


def construct_comment_for_rotation_scan() -> str:
    return
