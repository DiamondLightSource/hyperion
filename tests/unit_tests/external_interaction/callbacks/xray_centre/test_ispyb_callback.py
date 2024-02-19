from unittest.mock import MagicMock, patch

from hyperion.external_interaction.callbacks.xray_centre.ispyb_callback import (
    GridscanISPyBCallback,
)
from unit_tests.external_interaction.callbacks.conftest import TestData
from unit_tests.external_interaction.conftest import (
    EXPECTED_START_TIME,
    TEST_DATA_COLLECTION_GROUP_ID,
    TEST_SESSION_ID,
    assert_upsert_call_with,
    mx_acquisition_from_conn,
)
from unit_tests.external_interaction.ispyb.conftest import TEST_BARCODE, TEST_SAMPLE_ID


@patch(
    "hyperion.external_interaction.ispyb.ispyb_store.get_current_time_string",
    new=MagicMock(return_value=EXPECTED_START_TIME),
)
def test_activity_gated_start_2d(mock_ispyb_conn):
    callback = GridscanISPyBCallback()
    callback.activity_gated_start(TestData.test_gridscan2d_start_document)
    mx_acq = mx_acquisition_from_conn(mock_ispyb_conn)
    assert_upsert_call_with(
        mx_acq.upsert_data_collection_group.mock_calls[0],  # pyright: ignore
        mx_acq.get_data_collection_group_params(),
        {
            "parentid": TEST_SESSION_ID,
            "experimenttype": "mesh",
            "sampleid": TEST_SAMPLE_ID,
            "sample_barcode": TEST_BARCODE,  # deferred
        },
    )
    assert_upsert_call_with(
        mx_acq.upsert_data_collection.mock_calls[0],
        mx_acq.get_data_collection_params(),
        {
            "visitid": TEST_SESSION_ID,
            "parentid": TEST_DATA_COLLECTION_GROUP_ID,
            "sampleid": TEST_SAMPLE_ID,
            "detectorid": 78,
            "axisstart": 0.0,
            "axisrange": 0,
            "axisend": 0,
            "focal_spot_size_at_samplex": 0.0,
            "focal_spot_size_at_sampley": 0.0,
            "slitgap_vertical": 0.1,
            "slitgap_horizontal": 0.1,
            "beamsize_at_samplex": 0.1,
            "beamsize_at_sampley": 0.1,
            "transmission": 100.0,
            "comments": "Hyperion: Xray centring - Diffraction grid scan of 40 by 20 "
            "images in 100.0 um by 100.0 um steps. Top left (px): [50,100], "
            "bottom right (px): [450,300].",
            "data_collection_number": 0,
            "detector_distance": 100.0,
            "exp_time": 0.1,
            "imgdir": "/tmp/",
            "imgprefix": "file_name",
            "imgsuffix": "h5",
            "n_passes": 1,
            "overlap": 0,
            "flux": 10.0,
            "omegastart": 0,
            "start_image_number": 1,
            "resolution": 1.0,  # deferred
            "wavelength": 0,
            "xbeam": 150.0,
            "ybeam": 160.0,
            "xtal_snapshot1": "test_1_y",
            "xtal_snapshot2": "test_2_y",
            "xtal_snapshot3": "test_3_y",
            "synchrotron_mode": None,
            "undulator_gap1": 1.0,
            "starttime": EXPECTED_START_TIME,
            "filetemplate": "file_name_0_master.h5",
            "nimages": 40 * 20,
        },
    )
    mx_acq.upsert_data_collection.update_dc_position.assert_not_called()
    mx_acq.upsert_data_collection.update_dc_grid.assert_not_called()
