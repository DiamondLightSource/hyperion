from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Union

from dodal.devices.detector import DetectorParams
from numpy import ndarray

from hyperion.external_interaction.ispyb.data_model import (
    DataCollectionGroupInfo,
    DataCollectionInfo,
    DataCollectionPositionInfo,
)
from hyperion.external_interaction.ispyb.ispyb_dataclass import IspybParams
from hyperion.external_interaction.ispyb.ispyb_store import (
    EIGER_FILE_SUFFIX,
    I03_EIGER_DETECTOR,
)
from hyperion.external_interaction.ispyb.ispyb_utils import (
    VISIT_PATH_REGEX,
    get_current_time_string,
)
from hyperion.log import ISPYB_LOGGER


def populate_data_collection_group(experiment_type, detector_params, ispyb_params):
    dcg_info = DataCollectionGroupInfo(
        visit_string=get_visit_string(ispyb_params, detector_params),
        experiment_type=experiment_type,
        sample_id=ispyb_params.sample_id,
        sample_barcode=ispyb_params.sample_barcode,
    )
    return dcg_info


def populate_data_collection_position_info(ispyb_params):
    # explicit cast to float because numpy int64, grrr...
    dc_pos_info = DataCollectionPositionInfo(
        float(ispyb_params.position[0]),
        float(ispyb_params.position[1]),
        float(ispyb_params.position[2]),
    )
    return dc_pos_info


def populate_remaining_data_collection_info(
    comment_constructor,
    data_collection_group_id,
    data_collection_info: DataCollectionInfo,
    detector_params,
    ispyb_params,
):
    data_collection_info.visit_string = get_visit_string(ispyb_params, detector_params)
    data_collection_info.parent_id = data_collection_group_id
    data_collection_info.sample_id = ispyb_params.sample_id
    data_collection_info.detector_id = I03_EIGER_DETECTOR
    data_collection_info.axis_start = data_collection_info.omega_start
    data_collection_info.focal_spot_size_at_samplex = ispyb_params.focal_spot_size_x
    data_collection_info.focal_spot_size_at_sampley = ispyb_params.focal_spot_size_y
    data_collection_info.slitgap_vertical = ispyb_params.slit_gap_size_y
    data_collection_info.slitgap_horizontal = ispyb_params.slit_gap_size_x
    data_collection_info.beamsize_at_samplex = ispyb_params.beam_size_x
    data_collection_info.beamsize_at_sampley = ispyb_params.beam_size_y
    # Ispyb wants the transmission in a percentage, we use fractions
    data_collection_info.transmission = ispyb_params.transmission_fraction * 100
    data_collection_info.comments = comment_constructor()
    data_collection_info.detector_distance = detector_params.detector_distance
    data_collection_info.exp_time = detector_params.exposure_time
    data_collection_info.imgdir = detector_params.directory
    data_collection_info.imgprefix = detector_params.prefix
    data_collection_info.imgsuffix = EIGER_FILE_SUFFIX
    # Both overlap and n_passes included for backwards compatibility,
    # planned to be removed later
    data_collection_info.n_passes = 1
    data_collection_info.overlap = 0
    data_collection_info.flux = ispyb_params.flux
    data_collection_info.start_image_number = 1
    data_collection_info.resolution = ispyb_params.resolution
    data_collection_info.wavelength = ispyb_params.wavelength_angstroms
    beam_position = detector_params.get_beam_position_mm(
        detector_params.detector_distance
    )
    data_collection_info.xbeam = beam_position[0]
    data_collection_info.ybeam = beam_position[1]
    data_collection_info.synchrotron_mode = ispyb_params.synchrotron_mode
    data_collection_info.undulator_gap1 = ispyb_params.undulator_gap
    data_collection_info.start_time = get_current_time_string()
    # temporary file template until nxs filewriting is integrated and we can use
    # that file name
    data_collection_info.file_template = f"{detector_params.prefix}_{data_collection_info.data_collection_number}_master.h5"
    return data_collection_info


def get_visit_string_from_path(path: Optional[str]) -> Optional[str]:
    match = re.search(VISIT_PATH_REGEX, path) if path else None
    return str(match.group(1)) if match else None


def get_visit_string(ispyb_params: IspybParams, detector_params: DetectorParams) -> str:
    assert ispyb_params and detector_params, "StoreInISPyB didn't acquire params"
    visit_path_match = get_visit_string_from_path(ispyb_params.visit_path)
    if visit_path_match:
        return visit_path_match
    visit_path_match = get_visit_string_from_path(detector_params.directory)
    if not visit_path_match:
        raise ValueError(
            f"Visit not found from {ispyb_params.visit_path} or {detector_params.directory}"
        )
    return visit_path_match


def get_xtal_snapshots(ispyb_params):
    if ispyb_params.xtal_snapshots_omega_start:
        xtal_snapshots = ispyb_params.xtal_snapshots_omega_start[:3]
        ISPYB_LOGGER.info(
            f"Using rotation scan snapshots {xtal_snapshots} for ISPyB deposition"
        )
    else:
        ISPYB_LOGGER.warning("No xtal snapshot paths sent to ISPyB!")
        xtal_snapshots = []
    return xtal_snapshots + [None] * (3 - len(xtal_snapshots))


@dataclass
class GridScanInfo:
    upper_left: Union[list[int], ndarray]
    y_steps: int
    y_step_size: float
