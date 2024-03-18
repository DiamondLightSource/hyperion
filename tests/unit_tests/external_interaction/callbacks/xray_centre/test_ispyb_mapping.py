import numpy as np
import pytest

from hyperion.external_interaction.callbacks.common.ispyb_mapping import GridScanInfo
from hyperion.external_interaction.callbacks.xray_centre.ispyb_mapping import (
    populate_xy_data_collection_info,
)
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)

from ...conftest import (
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
    grid_scan_info = GridScanInfo(
        dummy_params.hyperion_params.ispyb_params.upper_left,
        3,
        dummy_params.experiment_params.y_step_size,
    )
    actual = populate_xy_data_collection_info(
        grid_scan_info,
        dummy_params,
        dummy_params.hyperion_params.ispyb_params,
        dummy_params.hyperion_params.detector_params,
    )

    assert actual.n_images == expected_number_of_steps
