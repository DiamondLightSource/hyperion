import re
from unittest.mock import mock_open, patch

import pytest
from ispyb.sp.mxacquisition import MXAcquisition
from mockito import ANY, mock, when
from src.artemis.ispyb.store_in_ispyb_2d import StoreInIspyb2D
from src.artemis.ispyb.store_in_ispyb_3d import StoreInIspyb3D
from src.artemis.parameters import FullParameters

TEST_DATA_COLLECTION_ID = 12
TEST_DATA_COLLECTION_GROUP_ID = 34
TEST_GRID_INFO_ID = 56
TEST_POSITION_ID = 78
TEST_SESSION_ID = 90

DCG_PARAMS = MXAcquisition.get_data_collection_group_params()
DC_PARAMS = MXAcquisition.get_data_collection_params()
GRID_PARAMS = MXAcquisition.get_dc_grid_params()
POSITION_PARAMS = MXAcquisition.get_dc_position_params()

DUMMY_CONFIG = "/file/path/to/config/"
DUMMY_PARAMS = FullParameters()

TIME_FORMAT_REGEX = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"


@pytest.fixture
def dummy_ispyb():
    return StoreInIspyb2D(DUMMY_CONFIG)


@pytest.fixture
def dummy_ispyb_3d():
    return StoreInIspyb3D(DUMMY_CONFIG)


def test_get_current_time_string(dummy_ispyb):
    current_time = dummy_ispyb.get_current_time_string()

    assert type(current_time) == str
    assert re.match(TIME_FORMAT_REGEX, current_time) != None


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
def test_store_grid_scan(ispyb_conn, dummy_ispyb):
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

    assert dummy_ispyb.store_grid_scan(DUMMY_PARAMS) == (
        [TEST_DATA_COLLECTION_ID],
        [TEST_GRID_INFO_ID],
    )


@patch("ispyb.open", new_callable=mock_open)
def test_store_3d_grid_scan(ispyb_conn, dummy_ispyb_3d):
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

    assert dummy_ispyb_3d.experiment_type == "Mesh3D"

    assert dummy_ispyb_3d.store_grid_scan(DUMMY_PARAMS) == (
        [TEST_DATA_COLLECTION_ID, TEST_DATA_COLLECTION_ID],
        [TEST_GRID_INFO_ID, TEST_GRID_INFO_ID],
    )

    assert dummy_ispyb_3d.omega_start == DUMMY_PARAMS.detector_params.omega_start - 90
    assert dummy_ispyb_3d.run_number == DUMMY_PARAMS.detector_params.run_number + 1


@patch("ispyb.open", new_callable=mock_open)
def test_param_keys(ispyb_conn, dummy_ispyb):
    ispyb_conn.return_value.core = mock()
    ispyb_conn.return_value.mx_acquisition = mock()

    mx_acquisition = ispyb_conn.return_value.mx_acquisition

    when(mx_acquisition).get_data_collection_group_params().thenReturn(DCG_PARAMS)
    when(mx_acquisition).get_data_collection_params().thenReturn(DC_PARAMS)
    when(mx_acquisition).get_dc_grid_params().thenReturn(GRID_PARAMS)
    when(mx_acquisition).get_dc_position_params().thenReturn(POSITION_PARAMS)

    when(ispyb_conn.return_value.core).retrieve_visit_id(ANY).thenReturn(
        TEST_SESSION_ID
    )
    when(mx_acquisition).upsert_data_collection(ANY).thenReturn(TEST_DATA_COLLECTION_ID)
    when(mx_acquisition).update_dc_position(ANY).thenReturn(TEST_POSITION_ID)
    when(mx_acquisition).upsert_data_collection_group(ANY).thenReturn(
        TEST_DATA_COLLECTION_GROUP_ID
    )
    when(mx_acquisition).upsert_dc_grid(ANY).thenReturn(TEST_GRID_INFO_ID)

    assert dummy_ispyb.store_grid_scan(DUMMY_PARAMS) == (
        [TEST_DATA_COLLECTION_ID],
        [TEST_GRID_INFO_ID],
    )
