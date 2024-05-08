from __future__ import annotations

from hyperion.external_interaction.callbacks.common.ispyb_mapping import (
    get_xtal_snapshots,
)
from hyperion.external_interaction.ispyb.data_model import DataCollectionInfo
from hyperion.parameters.rotation import RotationScan


def populate_data_collection_info_for_rotation(full_params: RotationScan):
    info = DataCollectionInfo(
        omega_start=full_params.omega_start_deg,
        data_collection_number=full_params.detector_params.run_number,  # type:ignore # the validator always makes this int
        n_images=full_params.num_images,
        axis_range=full_params.rotation_increment_deg,
        axis_end=(full_params.omega_start_deg + full_params.scan_width_deg),
        kappa_start=full_params.kappa_start_deg,
    )
    (info.xtal_snapshot1, info.xtal_snapshot2, info.xtal_snapshot3) = (
        get_xtal_snapshots(full_params.ispyb_params)
    )
    return info
