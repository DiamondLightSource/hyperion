import numpy as np
import pytest

from hyperion.external_interaction.ispyb.gridscan_ispyb_store_2d import (
    Store2DGridscanInIspyb,
)
from hyperion.external_interaction.ispyb.gridscan_ispyb_store_3d import (
    Store3DGridscanInIspyb,
)
from hyperion.external_interaction.ispyb.rotation_ispyb_store import (
    StoreRotationInIspyb,
)
from hyperion.parameters.constants import CONST
from hyperion.parameters.external_parameters import from_file
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)

TEST_SAMPLE_ID = "0001"
TEST_BARCODE = "12345A"


def default_raw_params(
    json_file="tests/test_data/parameter_json_files/test_internal_parameter_defaults.json",
):
    return from_file(json_file)


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
    store_in_ispyb_3d = Store3DGridscanInIspyb(CONST.SIM.ISPYB_CONFIG)
    return store_in_ispyb_3d


@pytest.fixture
def dummy_rotation_ispyb(dummy_rotation_params):
    store_in_ispyb = StoreRotationInIspyb(CONST.SIM.ISPYB_CONFIG)
    return store_in_ispyb


@pytest.fixture
def dummy_2d_gridscan_ispyb(dummy_params):
    return Store2DGridscanInIspyb(CONST.SIM.ISPYB_CONFIG)
