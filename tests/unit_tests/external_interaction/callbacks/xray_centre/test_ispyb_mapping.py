import numpy as np
import pytest

from hyperion.external_interaction.callbacks.xray_centre.ispyb_mapping import (
    grid_scan_xy_from_internal_params,
    populate_data_collection_info,
)
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)
from unit_tests.external_interaction.conftest import (
    TEST_BARCODE,
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


def test_given_x_and_y_steps_different_from_total_images_when_grid_scan_stored_then_num_images_correct(
    dummy_params: GridscanInternalParameters,
):
    expected_number_of_steps = 200 * 3
    dummy_params.experiment_params.x_steps = 200
    dummy_params.experiment_params.y_steps = 3
    grid_scan_info = grid_scan_xy_from_internal_params(dummy_params)
    actual = populate_data_collection_info(grid_scan_info)

    assert actual.n_images == expected_number_of_steps
