from unittest.mock import MagicMock, patch

from hyperion.external_interaction.callbacks.xray_centre.ispyb_callback import (
    GridscanISPyBCallback,
)

from ...conftest import (
    EXPECTED_START_TIME,
    TEST_DATA_COLLECTION_GROUP_ID,
    TEST_DATA_COLLECTION_IDS,
    TEST_SAMPLE_ID,
    TEST_SESSION_ID,
    assert_upsert_call_with,
    mx_acquisition_from_conn,
)
from ..conftest import TestData

EXPECTED_DATA_COLLECTION_3D_XY = {
    "visitid": TEST_SESSION_ID,
    "parentid": TEST_DATA_COLLECTION_GROUP_ID,
    "sampleid": TEST_SAMPLE_ID,
    "detectorid": 78,
    "axisstart": 0.0,
    "axisrange": 0,
    "axisend": 0,
    "focal_spot_size_at_samplex": 0.0,
    "focal_spot_size_at_sampley": 0.0,
    "beamsize_at_samplex": 0.1,
    "beamsize_at_sampley": 0.1,
    "data_collection_number": 0,
    "detector_distance": 100.0,
    "exp_time": 0.1,
    "imgdir": "/tmp/",
    "imgprefix": "file_name",
    "imgsuffix": "h5",
    "n_passes": 1,
    "overlap": 0,
    "omegastart": 0,
    "start_image_number": 1,
    "wavelength": None,
    "xbeam": 150.0,
    "ybeam": 160.0,
    "synchrotron_mode": None,
    "undulator_gap1": None,
    "starttime": EXPECTED_START_TIME,
    "filetemplate": "file_name_0_master.h5",
}

EXPECTED_DATA_COLLECTION_3D_XZ = EXPECTED_DATA_COLLECTION_3D_XY | {
    "omegastart": 90,
    "axis_range": 0,
    "axisend": 90,
    "axisstart": 90,
    "data_collection_number": 1,
    "filetemplate": "file_name_1_master.h5",
}

EXPECTED_DATA_COLLECTION_2D = {
    "visitid": TEST_SESSION_ID,
    "parentid": TEST_DATA_COLLECTION_GROUP_ID,
    "sampleid": TEST_SAMPLE_ID,
    "detectorid": 78,
    "axisstart": 0.0,
    "axisrange": 0,
    "axisend": 0,
    "focal_spot_size_at_samplex": 0.0,
    "focal_spot_size_at_sampley": 0.0,
    "beamsize_at_samplex": 0.1,
    "beamsize_at_sampley": 0.1,
    "data_collection_number": 0,
    "detector_distance": 100.0,
    "exp_time": 0.1,
    "imgdir": "/tmp/",
    "imgprefix": "file_name",
    "imgsuffix": "h5",
    "n_passes": 1,
    "overlap": 0,
    "omegastart": 0,
    "start_image_number": 1,
    "wavelength": None,
    "xbeam": 150.0,
    "ybeam": 160.0,
    "synchrotron_mode": None,
    "undulator_gap1": None,
    "starttime": EXPECTED_START_TIME,
    "filetemplate": "file_name_0_master.h5",
}


@patch(
    "hyperion.external_interaction.callbacks.common.ispyb_mapping.get_current_time_string",
    new=MagicMock(return_value=EXPECTED_START_TIME),
)
class TestXrayCentreISPyBCallback:
    def test_activity_gated_start_3d(self, mock_ispyb_conn):
        callback = GridscanISPyBCallback()
        callback.activity_gated_start(
            TestData.test_gridscan3d_start_document
        )  # pyright: ignore
        mx_acq = mx_acquisition_from_conn(mock_ispyb_conn)
        assert_upsert_call_with(
            mx_acq.upsert_data_collection_group.mock_calls[0],  # pyright: ignore
            mx_acq.get_data_collection_group_params(),
            {
                "parentid": TEST_SESSION_ID,
                "experimenttype": "Mesh3D",
                "sampleid": TEST_SAMPLE_ID,
            },
        )
        assert_upsert_call_with(
            mx_acq.upsert_data_collection.mock_calls[0],
            mx_acq.get_data_collection_params(),
            EXPECTED_DATA_COLLECTION_3D_XY,
        )
        assert_upsert_call_with(
            mx_acq.upsert_data_collection.mock_calls[1],
            mx_acq.get_data_collection_params(),
            EXPECTED_DATA_COLLECTION_3D_XZ,
        )
        mx_acq.upsert_data_collection.update_dc_position.assert_not_called()
        mx_acq.upsert_data_collection.upsert_dc_grid.assert_not_called()

    def test_hardware_read_event_3d(self, mock_ispyb_conn):
        callback = GridscanISPyBCallback()
        callback.activity_gated_start(
            TestData.test_gridscan3d_start_document
        )  # pyright: ignore
        mx_acq = mx_acquisition_from_conn(mock_ispyb_conn)
        mx_acq.upsert_data_collection_group.reset_mock()
        mx_acq.upsert_data_collection.reset_mock()
        callback.activity_gated_descriptor(
            TestData.test_descriptor_document_pre_data_collection
        )
        callback.activity_gated_event(TestData.test_event_document_pre_data_collection)
        mx_acq.upsert_data_collection_group.assert_not_called()
        assert_upsert_call_with(
            mx_acq.upsert_data_collection.mock_calls[0],
            mx_acq.get_data_collection_params(),
            {
                "parentid": TEST_DATA_COLLECTION_GROUP_ID,
                "id": TEST_DATA_COLLECTION_IDS[0],
                "slitgaphorizontal": 0.1234,
                "slitgapvertical": 0.2345,
                "synchrotronmode": "User",
                "undulatorgap1": 1.234,
            },
        )
        assert_upsert_call_with(
            mx_acq.upsert_data_collection.mock_calls[1],
            mx_acq.get_data_collection_params(),
            {
                "parentid": TEST_DATA_COLLECTION_GROUP_ID,
                "id": TEST_DATA_COLLECTION_IDS[1],
                "slitgaphorizontal": 0.1234,
                "slitgapvertical": 0.2345,
                "synchrotronmode": "User",
                "undulatorgap1": 1.234,
            },
        )

    def test_flux_read_events_3d(self, mock_ispyb_conn):
        callback = GridscanISPyBCallback()
        callback.activity_gated_start(
            TestData.test_gridscan3d_start_document
        )  # pyright: ignore
        mx_acq = mx_acquisition_from_conn(mock_ispyb_conn)
        callback.activity_gated_descriptor(
            TestData.test_descriptor_document_pre_data_collection
        )
        callback.activity_gated_event(TestData.test_event_document_pre_data_collection)
        mx_acq.upsert_data_collection_group.reset_mock()
        mx_acq.upsert_data_collection.reset_mock()

        callback.activity_gated_descriptor(
            TestData.test_descriptor_document_during_data_collection
        )
        callback.activity_gated_event(
            TestData.test_event_document_during_data_collection
        )

        assert_upsert_call_with(
            mx_acq.upsert_data_collection.mock_calls[0],
            mx_acq.get_data_collection_params(),
            {
                "parentid": TEST_DATA_COLLECTION_GROUP_ID,
                "id": TEST_DATA_COLLECTION_IDS[0],
                "wavelength": 1.1164718451643736,
                "transmission": 100,
                "flux": 10,
                "resolution": 1.1830593328548429,
            },
        )
        assert_upsert_call_with(
            mx_acq.upsert_data_collection.mock_calls[1],
            mx_acq.get_data_collection_params(),
            {
                "parentid": TEST_DATA_COLLECTION_GROUP_ID,
                "id": TEST_DATA_COLLECTION_IDS[1],
                "wavelength": 1.1164718451643736,
                "transmission": 100,
                "flux": 10,
                "resolution": 1.1830593328548429,
            },
        )
        assert_upsert_call_with(
            mx_acq.update_dc_position.mock_calls[0],
            mx_acq.get_dc_position_params(),
            {
                "id": TEST_DATA_COLLECTION_IDS[0],
                "pos_x": 0,
                "pos_y": 0,
                "pos_z": 0,
            },
        )
        assert_upsert_call_with(
            mx_acq.update_dc_position.mock_calls[1],
            mx_acq.get_dc_position_params(),
            {
                "id": TEST_DATA_COLLECTION_IDS[1],
                "pos_x": 0,
                "pos_y": 0,
                "pos_z": 0,
            },
        )
        mx_acq.upsert_dc_grid.assert_not_called()

    def test_activity_gated_event_oav_snapshot_triggered(self, mock_ispyb_conn):
        callback = GridscanISPyBCallback()
        callback.activity_gated_start(
            TestData.test_gridscan3d_start_document
        )  # pyright: ignore
        mx_acq = mx_acquisition_from_conn(mock_ispyb_conn)
        mx_acq.upsert_data_collection_group.reset_mock()
        mx_acq.upsert_data_collection.reset_mock()

        callback.activity_gated_descriptor(
            TestData.test_descriptor_document_oav_snapshot
        )
        callback.activity_gated_event(TestData.test_event_document_oav_snapshot_xy)
        callback.activity_gated_event(TestData.test_event_document_oav_snapshot_xz)

        mx_acq.upsert_data_collection_group.assert_not_called()
        assert_upsert_call_with(
            mx_acq.upsert_data_collection.mock_calls[0],
            mx_acq.get_data_collection_params(),
            {
                "id": TEST_DATA_COLLECTION_IDS[0],
                "parentid": TEST_DATA_COLLECTION_GROUP_ID,
                "nimages": 40 * 20,
                "xtal_snapshot1": "test_1_y",
                "xtal_snapshot2": "test_2_y",
                "xtal_snapshot3": "test_3_y",
                "comments": "Hyperion: Xray centring - Diffraction grid scan of 40 by 20 "
                "images in 100.0 um by 120.0 um steps. Top left (px): [50,100], "
                "bottom right (px): [3250,1700].",
            },
        )
        assert_upsert_call_with(
            mx_acq.upsert_data_collection.mock_calls[1],
            mx_acq.get_data_collection_params(),
            {
                "id": TEST_DATA_COLLECTION_IDS[1],
                "parentid": TEST_DATA_COLLECTION_GROUP_ID,
                "nimages": 40 * 10,
                "xtal_snapshot1": "test_1_z",
                "xtal_snapshot2": "test_2_z",
                "xtal_snapshot3": "test_3_z",
                "comments": "Hyperion: Xray centring - Diffraction grid scan of 40 by 10 "
                "images in 100.0 um by 120.0 um steps. Top left (px): [50,0], "
                "bottom right (px): [3250,800].",
            },
        )
        assert_upsert_call_with(
            mx_acq.upsert_dc_grid.mock_calls[0],
            mx_acq.get_dc_grid_params(),
            {
                "parentid": TEST_DATA_COLLECTION_IDS[0],
                "dxinmm": 0.1,
                "dyinmm": 0.12,
                "stepsx": 40,
                "stepsy": 20,
                "micronsperpixelx": 1.25,
                "micronsperpixely": 1.5,
                "snapshotoffsetxpixel": 50,
                "snapshotoffsetypixel": 100,
                "orientation": "horizontal",
                "snaked": True,
            },
        )
        assert_upsert_call_with(
            mx_acq.upsert_dc_grid.mock_calls[1],
            mx_acq.get_dc_grid_params(),
            {
                "parentid": TEST_DATA_COLLECTION_IDS[1],
                "dxinmm": 0.1,
                "dyinmm": 0.12,
                "stepsx": 40,
                "stepsy": 10,
                "micronsperpixelx": 1.25,
                "micronsperpixely": 1.5,
                "snapshotoffsetxpixel": 50,
                "snapshotoffsetypixel": 0,
                "orientation": "horizontal",
                "snaked": True,
            },
        )
