from copy import deepcopy
from typing import Sequence
from unittest.mock import MagicMock, mock_open, patch

import numpy as np
import pytest
from ispyb.sp.mxacquisition import MXAcquisition

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
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)

TEST_SAMPLE_ID = "0001"
TEST_BARCODE = "12345A"
TEST_DATA_COLLECTION_IDS = (12, 13)
TEST_DATA_COLLECTION_GROUP_ID = 34
TEST_GRID_INFO_IDS = (56, 57)
TEST_POSITION_ID = 78
TEST_SESSION_ID = 90


def default_raw_params(
    json_file="tests/test_data/parameter_json_files/test_internal_parameter_defaults.json",
):
    return from_file(json_file)


@pytest.fixture
def dummy_rotation_params():
    dummy_params = RotationInternalParameters(
        **default_raw_params(
            "tests/test_data/parameter_json_files/good_test_rotation_scan_parameters.json"
        )
    )
    dummy_params.hyperion_params.ispyb_params.sample_id = TEST_SAMPLE_ID
    dummy_params.hyperion_params.ispyb_params.sample_barcode = TEST_BARCODE
    return dummy_params


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
def base_ispyb_conn():
    with patch("ispyb.open", mock_open()) as ispyb_connection:
        mock_mx_acquisition = MagicMock()
        mock_mx_acquisition.get_data_collection_group_params.side_effect = (
            lambda: deepcopy(MXAcquisition.get_data_collection_group_params())
        )

        mock_mx_acquisition.get_data_collection_params.side_effect = lambda: deepcopy(
            MXAcquisition.get_data_collection_params()
        )
        mock_mx_acquisition.get_dc_position_params.side_effect = lambda: deepcopy(
            MXAcquisition.get_dc_position_params()
        )
        mock_mx_acquisition.get_dc_grid_params.side_effect = lambda: deepcopy(
            MXAcquisition.get_dc_grid_params()
        )
        ispyb_connection.return_value.mx_acquisition = mock_mx_acquisition
        mock_core = MagicMock()
        mock_core.retrieve_visit_id.return_value = TEST_SESSION_ID
        ispyb_connection.return_value.core = mock_core
        yield ispyb_connection


@pytest.fixture
def ispyb_conn_with_2x2_collections_and_grid_info(base_ispyb_conn):
    def upsert_data_collection(values):
        kvpairs = remap_upsert_columns(
            list(MXAcquisition.get_data_collection_params()), values
        )
        if kvpairs["id"]:
            return kvpairs["id"]
        else:
            return next(upsert_data_collection.i)  # pyright: ignore

    upsert_data_collection.i = iter(TEST_DATA_COLLECTION_IDS)  # pyright: ignore

    base_ispyb_conn.return_value.mx_acquisition.upsert_data_collection.side_effect = (
        upsert_data_collection
    )
    base_ispyb_conn.return_value.mx_acquisition.update_dc_position.return_value = (
        TEST_POSITION_ID
    )
    base_ispyb_conn.return_value.mx_acquisition.upsert_data_collection_group.return_value = (
        TEST_DATA_COLLECTION_GROUP_ID
    )

    def upsert_dc_grid(values):
        kvpairs = remap_upsert_columns(list(MXAcquisition.get_dc_grid_params()), values)
        if kvpairs["id"]:
            return kvpairs["id"]
        else:
            return next(upsert_dc_grid.i)  # pyright: ignore

    upsert_dc_grid.i = iter(TEST_GRID_INFO_IDS)  # pyright: ignore

    base_ispyb_conn.return_value.mx_acquisition.upsert_dc_grid.side_effect = (
        upsert_dc_grid
    )
    return base_ispyb_conn


@pytest.fixture
def dummy_3d_gridscan_ispyb(dummy_params):
    store_in_ispyb_3d = Store3DGridscanInIspyb(CONST.SIM.ISPYB_CONFIG)
    return store_in_ispyb_3d


def remap_upsert_columns(keys: Sequence[str], values: list):
    return dict(zip(keys, values))


@pytest.fixture
def dummy_rotation_ispyb(dummy_rotation_params):
    store_in_ispyb = StoreRotationInIspyb(CONST.SIM.ISPYB_CONFIG)
    return store_in_ispyb


@pytest.fixture
def dummy_2d_gridscan_ispyb(dummy_params):
    return Store2DGridscanInIspyb(CONST.SIM.ISPYB_CONFIG)


def mx_acquisition_from_conn(mock_ispyb_conn) -> MagicMock:
    return mock_ispyb_conn.return_value.__enter__.return_value.mx_acquisition


def assert_upsert_call_with(call, param_template, expected: dict):
    actual = remap_upsert_columns(list(param_template), call.args[0])
    assert actual == dict(param_template | expected)
