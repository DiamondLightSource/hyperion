from copy import deepcopy

import numpy as np
import pytest

from hyperion.external_interaction.ispyb.data_model import (
    DataCollectionGridInfo,
    DataCollectionPositionInfo,
    ExperimentType,
)
from hyperion.external_interaction.ispyb.ispyb_dataclass import Orientation
from hyperion.external_interaction.ispyb.ispyb_store import StoreInIspyb
from hyperion.parameters.constants import CONST
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)

from ..conftest import (
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
def dummy_3d_gridscan_ispyb():
    store_in_ispyb_3d = StoreInIspyb(CONST.SIM.ISPYB_CONFIG, ExperimentType.GRIDSCAN_3D)
    return store_in_ispyb_3d


@pytest.fixture
def dummy_rotation_ispyb(dummy_rotation_params):
    store_in_ispyb = StoreInIspyb(CONST.SIM.ISPYB_CONFIG, ExperimentType.ROTATION)
    return store_in_ispyb


@pytest.fixture
def dummy_2d_gridscan_ispyb():
    return StoreInIspyb(CONST.SIM.ISPYB_CONFIG, ExperimentType.GRIDSCAN_2D)


@pytest.fixture
def scan_xy_data_info_for_update(scan_data_info_for_begin):
    scan_data_info_for_update = deepcopy(scan_data_info_for_begin)
    scan_data_info_for_update.data_collection_info.parent_id = (
        TEST_DATA_COLLECTION_GROUP_ID
    )
    scan_data_info_for_update.data_collection_grid_info = DataCollectionGridInfo(
        dx_in_mm=0.1,
        dy_in_mm=0.1,
        steps_x=40,
        steps_y=20,
        microns_per_pixel_x=1.25,
        microns_per_pixel_y=1.25,
        snapshot_offset_x_pixel=100,
        snapshot_offset_y_pixel=100,
        orientation=Orientation.HORIZONTAL,
        snaked=True,
    )
    scan_data_info_for_update.data_collection_position_info = (
        DataCollectionPositionInfo(0, 0, 0)
    )
    return scan_data_info_for_update
