from copy import deepcopy

import numpy as np
import pytest

from hyperion.external_interaction.callbacks.common.ispyb_mapping import (
    GridScanInfo,
    populate_data_collection_position_info,
)
from hyperion.external_interaction.callbacks.xray_centre.ispyb_mapping import (
    populate_data_collection_grid_info,
)
from hyperion.external_interaction.ispyb.data_model import ExperimentType
from hyperion.external_interaction.ispyb.ispyb_store import StoreInIspyb
from hyperion.parameters.constants import CONST
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)
from unit_tests.external_interaction.conftest import (
    TEST_BARCODE,
    TEST_DATA_COLLECTION_GROUP_ID,
    TEST_SAMPLE_ID,
    default_raw_params,
)


@pytest.fixture
def dummy_params():
    dummy_params = GridscanInternalParameters(**default_raw_params())
    dummy_params.hyperion_params.ispyb_params.sample_id = TEST_SAMPLE_ID
    dummy_params.hyperion_params.ispyb_params.sample_barcode = TEST_BARCODE
    dummy_params.hyperion_params.ispyb_params.upper_left = np.array([100, 100, 50])
    dummy_params.hyperion_params.ispyb_params.microns_per_pixel_x = 1.25
    dummy_params.hyperion_params.ispyb_params.microns_per_pixel_y = 1.25
    dummy_params.hyperion_params.detector_params.run_number = 0
    return dummy_params


@pytest.fixture
def dummy_3d_gridscan_ispyb(dummy_params):
    store_in_ispyb_3d = StoreInIspyb(CONST.SIM.ISPYB_CONFIG, ExperimentType.GRIDSCAN_3D)
    return store_in_ispyb_3d


@pytest.fixture
def dummy_rotation_ispyb(dummy_rotation_params):
    store_in_ispyb = StoreInIspyb(CONST.SIM.ISPYB_CONFIG, ExperimentType.ROTATION)
    return store_in_ispyb


@pytest.fixture
def dummy_2d_gridscan_ispyb(dummy_params):
    return StoreInIspyb(CONST.SIM.ISPYB_CONFIG, ExperimentType.GRIDSCAN_2D)


@pytest.fixture
def scan_xy_data_info_for_update(dummy_params, scan_data_info_for_begin):
    scan_data_info_for_update = deepcopy(scan_data_info_for_begin)
    grid_scan_info = GridScanInfo(
        dummy_params.hyperion_params.ispyb_params.upper_left,
        dummy_params.experiment_params.y_steps,
        dummy_params.experiment_params.y_step_size,
    )
    scan_data_info_for_update.data_collection_info.parent_id = (
        TEST_DATA_COLLECTION_GROUP_ID
    )
    scan_data_info_for_update.data_collection_grid_info = (
        populate_data_collection_grid_info(
            dummy_params, grid_scan_info, dummy_params.hyperion_params.ispyb_params
        )
    )
    scan_data_info_for_update.data_collection_position_info = (
        populate_data_collection_position_info(
            dummy_params.hyperion_params.ispyb_params
        )
    )
    return scan_data_info_for_update
