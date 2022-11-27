import re
from unittest.mock import MagicMock, mock_open, patch

import pytest
from ispyb.sp.mxacquisition import MXAcquisition
from mockito import mock, when

from artemis.external_interaction.ispyb.store_in_ispyb import (
    StoreInIspyb2D,
    StoreInIspyb3D,
)
from artemis.parameters import FullParameters
from artemis.utils import Point3D

TEST_DATA_COLLECTION_ID = 12
TEST_DATA_COLLECTION_GROUP_ID = 34
TEST_GRID_INFO_ID = 56
TEST_POSITION_ID = 78
TEST_SESSION_ID = 90

DUMMY_CONFIG = "/file/path/to/config/"
TIME_FORMAT_REGEX = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"


@pytest.fixture
def dummy_params():
    dummy_params = FullParameters()
    dummy_params.ispyb_params.upper_left = Point3D(100, 100, 50)
    dummy_params.ispyb_params.pixels_per_micron_x = 0.8
    dummy_params.ispyb_params.pixels_per_micron_y = 0.8
    return dummy_params


@pytest.fixture
def dummy_ispyb(dummy_params):
    return StoreInIspyb2D(DUMMY_CONFIG, dummy_params)


@pytest.fixture
def dummy_ispyb_3d(dummy_params):
    return StoreInIspyb3D(DUMMY_CONFIG, dummy_params)


def test_get_current_time_string(dummy_ispyb):
    current_time = dummy_ispyb.get_current_time_string()

    assert type(current_time) == str
    assert re.match(TIME_FORMAT_REGEX, current_time) is not None


@pytest.mark.parametrize(
    "visit_path, expected_match",
    [
        ("/dls/i03/data/2022/cm6477-45/", "cm6477-45"),
        ("/dls/i03/data/2022/mx54663-1/", "mx54663-1"),
        ("/dls/i03/data/2022/mx53-1/", None),
        ("/dls/i03/data/2022/mx5563-1565/", None),
    ],
)
def test_regex_string(dummy_ispyb, visit_path: str, expected_match: str):
    assert dummy_ispyb.get_visit_string_from_path(visit_path) == expected_match


@patch("ispyb.open", new_callable=mock_open)
def test_store_grid_scan(ispyb_conn, dummy_ispyb, dummy_params):
    ispyb_conn.return_value.mx_acquisition = mock()
    ispyb_conn.return_value.core = mock()

    when(dummy_ispyb)._store_position_table(TEST_DATA_COLLECTION_ID).thenReturn(
        TEST_POSITION_ID
    )
    when(dummy_ispyb)._store_data_collection_group_table().thenReturn(
        TEST_DATA_COLLECTION_GROUP_ID
    )
    when(dummy_ispyb)._store_data_collection_table(
        TEST_DATA_COLLECTION_GROUP_ID
    ).thenReturn(TEST_DATA_COLLECTION_ID)
    when(dummy_ispyb)._store_grid_info_table(TEST_DATA_COLLECTION_ID).thenReturn(
        TEST_GRID_INFO_ID
    )

    assert dummy_ispyb.experiment_type == "mesh"

    assert dummy_ispyb.store_grid_scan(dummy_params) == (
        [TEST_DATA_COLLECTION_ID],
        [TEST_GRID_INFO_ID],
        TEST_DATA_COLLECTION_GROUP_ID,
    )


@patch("ispyb.open", new_callable=mock_open)
def test_store_3d_grid_scan(ispyb_conn, dummy_ispyb_3d, dummy_params):
    ispyb_conn.return_value.mx_acquisition = mock()
    ispyb_conn.return_value.core = mock()

    when(dummy_ispyb_3d)._store_position_table(TEST_DATA_COLLECTION_ID).thenReturn(
        TEST_POSITION_ID
    )
    when(dummy_ispyb_3d)._store_data_collection_group_table().thenReturn(
        TEST_DATA_COLLECTION_GROUP_ID
    )
    when(dummy_ispyb_3d)._store_data_collection_table(
        TEST_DATA_COLLECTION_GROUP_ID
    ).thenReturn(TEST_DATA_COLLECTION_ID)
    when(dummy_ispyb_3d)._store_grid_info_table(TEST_DATA_COLLECTION_ID).thenReturn(
        TEST_GRID_INFO_ID
    )

    x = 0
    y = 1
    z = 2
    dummy_params.ispyb_params.upper_left = Point3D(x, y, z)
    dummy_params.grid_scan_params.z_step_size = 0.2

    assert dummy_ispyb_3d.experiment_type == "Mesh3D"

    assert dummy_ispyb_3d.store_grid_scan(dummy_params) == (
        [TEST_DATA_COLLECTION_ID, TEST_DATA_COLLECTION_ID],
        [TEST_GRID_INFO_ID, TEST_GRID_INFO_ID],
        TEST_DATA_COLLECTION_GROUP_ID,
    )

    assert dummy_ispyb_3d.omega_start == dummy_params.detector_params.omega_start + 90
    assert dummy_ispyb_3d.run_number == dummy_params.detector_params.run_number + 1
    assert (
        dummy_ispyb_3d.xtal_snapshots
        == dummy_params.ispyb_params.xtal_snapshots_omega_end
    )
    assert dummy_ispyb_3d.y_step_size == dummy_params.grid_scan_params.z_step_size
    assert dummy_ispyb_3d.y_steps == dummy_params.grid_scan_params.z_steps
    assert dummy_ispyb_3d.upper_left.x == x
    assert dummy_ispyb_3d.upper_left.y == z


def setup_mock_return_values(ispyb_conn):

    mx_acquisition = ispyb_conn.return_value.__enter__.return_value.mx_acquisition

    dcg_params = MXAcquisition.get_data_collection_group_params()
    dc_params = MXAcquisition.get_data_collection_params()
    grid_params = MXAcquisition.get_dc_grid_params()
    position_params = MXAcquisition.get_dc_position_params()

    mx_acquisition.get_data_collection_group_params.return_value = dcg_params
    mx_acquisition.get_data_collection_params.return_value = dc_params
    mx_acquisition.get_dc_grid_params.return_value = grid_params
    mx_acquisition.get_dc_position_params.return_value = position_params

    ispyb_conn.return_value.core.retrieve_visit_id.return_value = TEST_SESSION_ID
    mx_acquisition.upsert_data_collection.return_value = TEST_DATA_COLLECTION_ID
    mx_acquisition.update_dc_position.return_value = TEST_POSITION_ID
    mx_acquisition.upsert_data_collection_group.return_value = (
        TEST_DATA_COLLECTION_GROUP_ID
    )
    mx_acquisition.upsert_dc_grid.return_value = TEST_GRID_INFO_ID


@patch("ispyb.open")
def test_param_keys(ispyb_conn, dummy_ispyb, dummy_params):
    setup_mock_return_values(ispyb_conn)

    assert dummy_ispyb.store_grid_scan(dummy_params) == (
        [TEST_DATA_COLLECTION_ID],
        [TEST_GRID_INFO_ID],
        TEST_DATA_COLLECTION_GROUP_ID,
    )


def _test_when_grid_scan_stored_then_data_present_in_upserts(
    ispyb_conn, dummy_ispyb, dummy_params, test_function, test_group=False
):
    setup_mock_return_values(ispyb_conn)

    dummy_ispyb.store_grid_scan(dummy_params)

    mx_acquisition = ispyb_conn.return_value.__enter__.return_value.mx_acquisition

    upsert_data_collection_arg_list = (
        mx_acquisition.upsert_data_collection.call_args_list[0][0]
    )
    actual = upsert_data_collection_arg_list[0]
    assert test_function(MXAcquisition.get_data_collection_params(), actual)

    if test_group:
        upsert_data_collection_group_arg_list = (
            mx_acquisition.upsert_data_collection_group.call_args_list[0][0]
        )
        actual = upsert_data_collection_group_arg_list[0]
        assert test_function(MXAcquisition.get_data_collection_group_params(), actual)


@patch("ispyb.open")
def test_given_sampleid_of_none_when_grid_scan_stored_then_sample_id_not_set(
    ispyb_conn, dummy_ispyb, dummy_params
):
    def test_sample_id(default_params, actual):
        sampleid_idx = list(default_params).index("sampleid")
        return actual[sampleid_idx] == default_params["sampleid"]

    _test_when_grid_scan_stored_then_data_present_in_upserts(
        ispyb_conn, dummy_ispyb, dummy_params, test_sample_id, True
    )


@patch("ispyb.open")
def test_given_real_sampleid_when_grid_scan_stored_then_sample_id_set(
    ispyb_conn, dummy_ispyb, dummy_params
):
    expected_sample_id = "0001"
    dummy_params.ispyb_params.sample_id = expected_sample_id

    def test_sample_id(default_params, actual):
        sampleid_idx = list(default_params).index("sampleid")
        return actual[sampleid_idx] == expected_sample_id

    _test_when_grid_scan_stored_then_data_present_in_upserts(
        ispyb_conn, dummy_ispyb, dummy_params, test_sample_id, True
    )


@patch("ispyb.open")
def test_fail_result_run_results_in_bad_run_status(
    mock_ispyb_conn: MagicMock,
    dummy_ispyb: StoreInIspyb2D,
):
    setup_mock_return_values(mock_ispyb_conn)
    mock_mx_aquisition = (
        mock_ispyb_conn.return_value.__enter__.return_value.mx_acquisition
    )
    mock_upsert_data_collection = mock_mx_aquisition.upsert_data_collection

    dummy_ispyb.begin_deposition()
    dummy_ispyb.end_deposition("fail", "test specifies failure")

    mock_upsert_data_collection_calls = mock_upsert_data_collection.call_args_list
    mock_upsert_data_collection_second_call_args = mock_upsert_data_collection_calls[1][
        0
    ]
    upserted_param_value_list = mock_upsert_data_collection_second_call_args[0]
    assert "DataCollection Unsuccessful" in upserted_param_value_list
    assert "DataCollection Successful" not in upserted_param_value_list


@patch("ispyb.open")
def test_no_exception_during_run_results_in_good_run_status(
    mock_ispyb_conn: MagicMock,
    dummy_ispyb: StoreInIspyb2D,
):
    setup_mock_return_values(mock_ispyb_conn)
    mock_mx_aquisition = (
        mock_ispyb_conn.return_value.__enter__.return_value.mx_acquisition
    )
    mock_upsert_data_collection = mock_mx_aquisition.upsert_data_collection
    dummy_ispyb.begin_deposition()
    dummy_ispyb.end_deposition("success", "")
    mock_upsert_data_collection_calls = mock_upsert_data_collection.call_args_list
    mock_upsert_data_collection_second_call_args = mock_upsert_data_collection_calls[1][
        0
    ]
    upserted_param_value_list = mock_upsert_data_collection_second_call_args[0]
    assert "DataCollection Unsuccessful" not in upserted_param_value_list
    assert "DataCollection Successful" in upserted_param_value_list


@patch("ispyb.open")
def test_ispyb_deposition_comment_correct(
    mock_ispyb_conn: MagicMock,
    dummy_ispyb: StoreInIspyb2D,
):
    setup_mock_return_values(mock_ispyb_conn)
    mock_mx_aquisition = (
        mock_ispyb_conn.return_value.__enter__.return_value.mx_acquisition
    )
    mock_upsert_data_collection = mock_mx_aquisition.upsert_data_collection
    dummy_ispyb.begin_deposition()
    mock_upsert_call_args = mock_upsert_data_collection.call_args_list[0][0]

    upserted_param_value_list = mock_upsert_call_args[0]
    assert upserted_param_value_list[29] == (
        "Artemis: Xray centring - Diffraction grid scan of 4 by 200 images "
        "in 0.1 mm by 0.1 mm steps. Top left: [100,100], bottom right: [420,16100]."
    )


@patch("ispyb.open")
def test_ispyb_deposition_rounds_to_int(
    mock_ispyb_conn: MagicMock,
    dummy_ispyb: StoreInIspyb2D,
):
    setup_mock_return_values(mock_ispyb_conn)
    mock_mx_aquisition = (
        mock_ispyb_conn.return_value.__enter__.return_value.mx_acquisition
    )
    mock_upsert_data_collection = mock_mx_aquisition.upsert_data_collection
    dummy_ispyb.full_params.ispyb_params.upper_left = Point3D(0.01, 100, 50)
    dummy_ispyb.begin_deposition()
    mock_upsert_call_args = mock_upsert_data_collection.call_args_list[0][0]

    upserted_param_value_list = mock_upsert_call_args[0]
    assert upserted_param_value_list[29] == (
        "Artemis: Xray centring - Diffraction grid scan of 4 by 200 images "
        "in 0.1 mm by 0.1 mm steps. Top left: [0,100], bottom right: [320,16100]."
    )


@patch("ispyb.open")
def test_ispyb_deposition_comment_for_3D_correct(
    mock_ispyb_conn: MagicMock,
    dummy_ispyb_3d: StoreInIspyb3D,
):
    setup_mock_return_values(mock_ispyb_conn)
    mock_mx_aquisition = (
        mock_ispyb_conn.return_value.__enter__.return_value.mx_acquisition
    )
    mock_upsert_dc = mock_mx_aquisition.upsert_data_collection
    dummy_ispyb_3d.begin_deposition()
    first_upserted_param_value_list = mock_upsert_dc.call_args_list[0][0][0]
    second_upserted_param_value_list = mock_upsert_dc.call_args_list[1][0][0]
    assert first_upserted_param_value_list[29] == (
        "Artemis: Xray centring - Diffraction grid scan of 4 by 200 images "
        "in 0.1 mm by 0.1 mm steps. Top left: [100,100], bottom right: [420,16100]."
    )
    assert second_upserted_param_value_list[29] == (
        "Artemis: Xray centring - Diffraction grid scan of 4 by 61 images "
        "in 0.1 mm by 0.1 mm steps. Top left: [100,50], bottom right: [420,4930]."
    )


@patch("ispyb.open")
def test_ispyb_deposition_comment_correct_on_failure(
    mock_ispyb_conn: MagicMock,
    dummy_ispyb: StoreInIspyb2D,
):
    setup_mock_return_values(mock_ispyb_conn)
    mock_mx_aquisition = (
        mock_ispyb_conn.return_value.__enter__.return_value.mx_acquisition
    )
    mock_upsert_data_collection = mock_mx_aquisition.upsert_data_collection
    dummy_ispyb.begin_deposition()
    dummy_ispyb.end_deposition("fail", "could not connect to devices")
    mock_upsert_data_collection_calls = mock_upsert_data_collection.call_args_list
    mock_upsert_data_collection_second_call_args = mock_upsert_data_collection_calls[1][
        0
    ]
    upserted_param_value_list = mock_upsert_data_collection_second_call_args[0]
    assert upserted_param_value_list[29] == (
        "Artemis: Xray centring - Diffraction grid scan of 4 by 200 images "
        "in 0.1 mm by 0.1 mm steps. Top left: [100,100], bottom right: [420,16100]. "
        "DataCollection Unsuccessful reason: could not connect to devices"
    )


@patch("ispyb.open")
def test_given_x_and_y_steps_different_from_total_images_when_grid_scan_stored_then_num_images_correct(
    ispyb_conn, dummy_ispyb, dummy_params
):
    expected_number_of_steps = 200 * 3
    dummy_params.grid_scan_params.x_steps = 200
    dummy_params.grid_scan_params.y_steps = 3

    def test_number_of_steps(default_params, actual):
        # Note that internally the ispyb API removes underscores so this is the same as n_images
        number_of_steps_idx = list(default_params).index("nimages")
        return actual[number_of_steps_idx] == expected_number_of_steps

    _test_when_grid_scan_stored_then_data_present_in_upserts(
        ispyb_conn, dummy_ispyb, dummy_params, test_number_of_steps
    )
