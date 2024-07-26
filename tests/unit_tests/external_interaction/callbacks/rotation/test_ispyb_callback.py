from unittest.mock import MagicMock, patch

import pytest

from hyperion.external_interaction.callbacks.rotation.ispyb_callback import (
    RotationISPyBCallback,
)

from ...conftest import (
    EXPECTED_END_TIME,
    EXPECTED_START_TIME,
    TEST_DATA_COLLECTION_GROUP_ID,
    TEST_DATA_COLLECTION_IDS,
    TEST_SAMPLE_ID,
    TEST_SESSION_ID,
    assert_upsert_call_with,
    mx_acquisition_from_conn,
)
from ..conftest import TestData

EXPECTED_DATA_COLLECTION = {
    "visitid": TEST_SESSION_ID,
    "parentid": TEST_DATA_COLLECTION_GROUP_ID,
    "sampleid": TEST_SAMPLE_ID,
    "detectorid": 78,
    "axisstart": 0.0,
    "axisrange": 0.1,
    "axisend": 180,
    "comments": "test",
    "data_collection_number": 1,
    "detector_distance": 100.0,
    "exp_time": 0.1,
    "imgdir": "/tmp/dls/i03/data/2024/cm31105-4/auto/123456/",
    "imgprefix": "file_name",
    "imgsuffix": "h5",
    "n_passes": 1,
    "overlap": 0,
    "omegastart": 0,
    "start_image_number": 1,
    "xbeam": 150.0,
    "ybeam": 160.0,
    "synchrotron_mode": None,
    "starttime": EXPECTED_START_TIME,
    "filetemplate": "file_name_1_master.h5",
    "nimages": 1800,
    "kappastart": None,
}


@pytest.fixture
def rotation_start_outer_doc_without_snapshots(
    test_rotation_start_outer_document, dummy_rotation_params
):
    dummy_rotation_params.ispyb_extras.xtal_snapshots_omega_start = None
    test_rotation_start_outer_document["hyperion_parameters"] = (
        dummy_rotation_params.json()
    )
    return test_rotation_start_outer_document


@patch(
    "hyperion.external_interaction.callbacks.common.ispyb_mapping.get_current_time_string",
    new=MagicMock(return_value=EXPECTED_START_TIME),
)
def test_activity_gated_start(
    mock_ispyb_conn, rotation_start_outer_doc_without_snapshots
):
    callback = RotationISPyBCallback()

    callback.activity_gated_start(rotation_start_outer_doc_without_snapshots)
    mx = mx_acquisition_from_conn(mock_ispyb_conn)
    assert_upsert_call_with(
        mx.upsert_data_collection_group.mock_calls[0],
        mx.get_data_collection_group_params(),
        {
            "parentid": TEST_SESSION_ID,
            "experimenttype": "SAD",
            "sampleid": TEST_SAMPLE_ID,
        },
    )
    assert_upsert_call_with(
        mx.upsert_data_collection.mock_calls[0],
        mx.get_data_collection_params(),
        EXPECTED_DATA_COLLECTION,
    )


@patch(
    "hyperion.external_interaction.callbacks.common.ispyb_mapping.get_current_time_string",
    new=MagicMock(return_value=EXPECTED_START_TIME),
)
def test_activity_gated_start_with_snapshot_parameters(
    mock_ispyb_conn, test_rotation_start_outer_document
):
    callback = RotationISPyBCallback()

    callback.activity_gated_start(test_rotation_start_outer_document)
    mx = mx_acquisition_from_conn(mock_ispyb_conn)
    assert_upsert_call_with(
        mx.upsert_data_collection_group.mock_calls[0],
        mx.get_data_collection_group_params(),
        {
            "parentid": TEST_SESSION_ID,
            "experimenttype": "SAD",
            "sampleid": TEST_SAMPLE_ID,
        },
    )
    assert_upsert_call_with(
        mx.upsert_data_collection.mock_calls[0],
        mx.get_data_collection_params(),
        EXPECTED_DATA_COLLECTION
        | {
            "xtal_snapshot1": "test_1_y",
            "xtal_snapshot2": "test_2_y",
            "xtal_snapshot3": "test_3_y",
        },
    )


@patch(
    "hyperion.external_interaction.callbacks.common.ispyb_mapping.get_current_time_string",
    new=MagicMock(return_value=EXPECTED_START_TIME),
)
def test_hardware_read_events(
    mock_ispyb_conn, dummy_rotation_params, test_rotation_start_outer_document
):
    callback = RotationISPyBCallback()
    callback.activity_gated_start(test_rotation_start_outer_document)  # pyright: ignore
    callback.activity_gated_start(
        TestData.test_rotation_start_main_document  # pyright: ignore
    )
    mx = mx_acquisition_from_conn(mock_ispyb_conn)

    mx.upsert_data_collection_group.reset_mock()
    mx.upsert_data_collection.reset_mock()

    callback.activity_gated_descriptor(
        TestData.test_descriptor_document_pre_data_collection
    )
    callback.activity_gated_event(TestData.test_event_document_pre_data_collection)
    mx.upsert_data_collection_group.assert_not_called()
    assert_upsert_call_with(
        mx.upsert_data_collection.mock_calls[0],
        mx.get_data_collection_params(),
        {
            "parentid": TEST_DATA_COLLECTION_GROUP_ID,
            "id": TEST_DATA_COLLECTION_IDS[0],
            "slitgaphorizontal": 0.1234,
            "slitgapvertical": 0.2345,
            "synchrotronmode": "User",
            "undulatorgap1": 1.234,
            "comments": "Sample position (µm): (158, 24, 3) test ",
        },
    )
    expected_data = TestData.test_event_document_pre_data_collection["data"]
    assert_upsert_call_with(
        mx.update_dc_position.mock_calls[0],
        mx.get_dc_position_params(),
        {
            "id": TEST_DATA_COLLECTION_IDS[0],
            "pos_x": expected_data["smargon-x"],
            "pos_y": expected_data["smargon-y"],
            "pos_z": expected_data["smargon-z"],
        },
    )


@patch(
    "hyperion.external_interaction.callbacks.common.ispyb_mapping.get_current_time_string",
    new=MagicMock(return_value=EXPECTED_START_TIME),
)
def test_flux_read_events(
    mock_ispyb_conn, dummy_rotation_params, test_rotation_start_outer_document
):
    callback = RotationISPyBCallback()
    callback.activity_gated_start(test_rotation_start_outer_document)  # pyright: ignore
    callback.activity_gated_start(
        TestData.test_rotation_start_main_document  # pyright: ignore
    )
    mx = mx_acquisition_from_conn(mock_ispyb_conn)
    callback.activity_gated_descriptor(
        TestData.test_descriptor_document_pre_data_collection
    )
    callback.activity_gated_event(TestData.test_event_document_pre_data_collection)
    mx.upsert_data_collection_group.reset_mock()
    mx.upsert_data_collection.reset_mock()
    callback.activity_gated_descriptor(
        TestData.test_descriptor_document_during_data_collection
    )
    callback.activity_gated_event(
        TestData.test_rotation_event_document_during_data_collection
    )

    mx.upsert_data_collection_group.assert_not_called()
    assert_upsert_call_with(
        mx.upsert_data_collection.mock_calls[0],
        mx.get_data_collection_params(),
        {
            "parentid": TEST_DATA_COLLECTION_GROUP_ID,
            "id": TEST_DATA_COLLECTION_IDS[0],
            "focal_spot_size_at_samplex": 0.05,
            "focal_spot_size_at_sampley": 0.02,
            "beamsize_at_samplex": 0.05,
            "beamsize_at_sampley": 0.02,
            "wavelength": 1.1164718451643736,
            "transmission": 98,
            "flux": 9.81,
            "resolution": 1.1830593328548429,
        },
    )


@patch(
    "hyperion.external_interaction.callbacks.common.ispyb_mapping.get_current_time_string",
    new=MagicMock(return_value=EXPECTED_START_TIME),
)
def test_oav_rotation_snapshot_triggered_event(
    mock_ispyb_conn, dummy_rotation_params, rotation_start_outer_doc_without_snapshots
):
    callback = RotationISPyBCallback()
    callback.activity_gated_start(rotation_start_outer_doc_without_snapshots)  # pyright: ignore
    callback.activity_gated_start(
        TestData.test_rotation_start_main_document  # pyright: ignore
    )
    mx = mx_acquisition_from_conn(mock_ispyb_conn)
    callback.activity_gated_descriptor(
        TestData.test_descriptor_document_oav_rotation_snapshot
    )

    for snapshot in [
        {"filename": "snapshot_0", "colname": "xtal_snapshot1"},
        {"filename": "snapshot_90", "colname": "xtal_snapshot2"},
        {"filename": "snapshot_180", "colname": "xtal_snapshot3"},
        {"filename": "snapshot_270", "colname": "xtal_snapshot4"},
    ]:
        mx.upsert_data_collection.reset_mock()
        event_doc = dict(TestData.test_event_document_oav_rotation_snapshot)
        event_doc["data"]["oav_snapshot_last_saved_path"] = snapshot["filename"]  # type: ignore
        callback.activity_gated_event(
            TestData.test_event_document_oav_rotation_snapshot
        )
        mx.upsert_data_collection_group.reset_mock()
        assert_upsert_call_with(
            mx.upsert_data_collection.mock_calls[0],
            mx.get_data_collection_params(),
            {
                "parentid": TEST_DATA_COLLECTION_GROUP_ID,
                "id": TEST_DATA_COLLECTION_IDS[0],
                snapshot["colname"]: snapshot["filename"],
            },
        )

    mx.upsert_data_collection_group.assert_not_called()


@patch(
    "hyperion.external_interaction.callbacks.common.ispyb_mapping.get_current_time_string",
    new=MagicMock(return_value=EXPECTED_START_TIME),
)
def test_activity_gated_stop(mock_ispyb_conn, test_rotation_start_outer_document):
    callback = RotationISPyBCallback()
    callback.activity_gated_start(test_rotation_start_outer_document)  # pyright: ignore
    callback.activity_gated_start(
        TestData.test_rotation_start_main_document  # pyright: ignore
    )
    mx = mx_acquisition_from_conn(mock_ispyb_conn)

    mx.upsert_data_collection_group.reset_mock()
    mx.upsert_data_collection.reset_mock()

    with patch(
        "hyperion.external_interaction.ispyb.ispyb_store.get_current_time_string",
        new=MagicMock(return_value=EXPECTED_END_TIME),
    ):
        callback.activity_gated_stop(TestData.test_rotation_stop_main_document)

    assert mx.update_data_collection_append_comments.call_args_list[0] == (
        (
            TEST_DATA_COLLECTION_IDS[0],
            "DataCollection Successful reason: Test succeeded",
            " ",
        ),
    )
    assert_upsert_call_with(
        mx.upsert_data_collection.mock_calls[0],
        mx.get_data_collection_params(),
        {
            "id": TEST_DATA_COLLECTION_IDS[0],
            "parentid": TEST_DATA_COLLECTION_GROUP_ID,
            "endtime": EXPECTED_END_TIME,
            "runstatus": "DataCollection Successful",
        },
    )
    assert len(mx.upsert_data_collection.mock_calls) == 1


def test_comment_correct_after_hardware_read(
    mock_ispyb_conn, dummy_rotation_params, test_rotation_start_outer_document
):
    callback = RotationISPyBCallback()
    test_rotation_start_outer_document["hyperion_parameters"] = (
        test_rotation_start_outer_document[
            "hyperion_parameters"
        ].replace('"comment": "test"', '"comment": "a lovely unit test"')
    )
    callback.activity_gated_start(test_rotation_start_outer_document)  # pyright: ignore
    callback.activity_gated_start(
        TestData.test_rotation_start_main_document  # pyright: ignore
    )
    mx = mx_acquisition_from_conn(mock_ispyb_conn)

    mx.upsert_data_collection_group.reset_mock()
    mx.upsert_data_collection.reset_mock()

    callback.activity_gated_descriptor(
        TestData.test_descriptor_document_pre_data_collection
    )
    callback.activity_gated_event(TestData.test_event_document_pre_data_collection)
    assert_upsert_call_with(
        mx.upsert_data_collection.mock_calls[0],
        mx.get_data_collection_params(),
        {
            "parentid": TEST_DATA_COLLECTION_GROUP_ID,
            "id": TEST_DATA_COLLECTION_IDS[0],
            "slitgaphorizontal": 0.1234,
            "slitgapvertical": 0.2345,
            "synchrotronmode": "User",
            "undulatorgap1": 1.234,
            "comments": "Sample position (µm): (158, 24, 3) a lovely unit test ",
        },
    )
