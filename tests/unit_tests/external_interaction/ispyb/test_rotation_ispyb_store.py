from copy import deepcopy
from unittest.mock import MagicMock, mock_open, patch

import pytest
from mockito import mock

from hyperion.external_interaction.ispyb.ispyb_store import IspybIds
from hyperion.external_interaction.ispyb.rotation_ispyb_store import (
    StoreRotationInIspyb,
)
from hyperion.parameters.constants import SIM_ISPYB_CONFIG
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)

from .conftest import (
    TEST_BARCODE,
    TEST_DATA_COLLECTION_GROUP_ID,
    TEST_DATA_COLLECTION_IDS,
    TEST_SAMPLE_ID,
    TEST_SESSION_ID,
    assert_upsert_call_with,
    mx_acquisition_from_conn,
)
from .test_gridscan_ispyb_store_2d import (
    EMPTY_DATA_COLLECTION_PARAMS,
)

EXPECTED_START_TIME = "2024-02-08 14:03:59"
EXPECTED_END_TIME = "2024-02-08 14:04:01"


@patch(
    "hyperion.external_interaction.ispyb.ispyb_store.get_current_time_string",
    new=MagicMock(return_value=EXPECTED_START_TIME),
)
def test_begin_deposition(
    ispyb_conn_with_2x2_collections_and_grid_info,
    dummy_rotation_ispyb,
    dummy_rotation_params,
):
    assert dummy_rotation_ispyb.begin_deposition() == IspybIds(
        data_collection_ids=TEST_DATA_COLLECTION_IDS[0],
        data_collection_group_id=TEST_DATA_COLLECTION_GROUP_ID,
    )
    mx_acq = mx_acquisition_from_conn(ispyb_conn_with_2x2_collections_and_grid_info)
    assert_upsert_call_with(
        mx_acq.upsert_data_collection_group.mock_calls[0],
        mx_acq.get_data_collection_group_params(),
        {
            "parentid": TEST_SESSION_ID,
            "experimenttype": "SAD",
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
            "axisrange": 0.1,
            "axisend": 180,
            "focal_spot_size_at_samplex": 1.0,
            "focal_spot_size_at_sampley": 1.0,
            "slitgap_vertical": 1,
            "slitgap_horizontal": 1,
            "beamsize_at_samplex": 1,
            "beamsize_at_sampley": 1,
            "transmission": 100.0,
            "comments": "Hyperion rotation scan",
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
            "wavelength": 123.98419840550369,
            "xbeam": 150.0,
            "ybeam": 160.0,
            "xtal_snapshot1": "test_1_y",
            "xtal_snapshot2": "test_2_y",
            "xtal_snapshot3": "test_3_y",
            "synchrotron_mode": None,
            "starttime": EXPECTED_START_TIME,
            "filetemplate": "file_name_0_master.h5",
            "nimages": 1800,
            "kappastart": 0,
        },
    )


@patch(
    "hyperion.external_interaction.ispyb.ispyb_store.get_current_time_string",
    new=MagicMock(return_value=EXPECTED_START_TIME),
)
def test_update_deposition(
    ispyb_conn_with_2x2_collections_and_grid_info,
    dummy_rotation_ispyb,
    dummy_rotation_params,
):
    dummy_rotation_ispyb.begin_deposition()
    mx_acq = mx_acquisition_from_conn(ispyb_conn_with_2x2_collections_and_grid_info)
    mx_acq.upsert_data_collection_group.reset_mock()
    mx_acq.upsert_data_collection.reset_mock()

    assert dummy_rotation_ispyb.update_deposition() == IspybIds(
        data_collection_group_id=TEST_DATA_COLLECTION_GROUP_ID,
        data_collection_ids=TEST_DATA_COLLECTION_IDS[0],
    )
    assert_upsert_call_with(
        mx_acq.upsert_data_collection_group.mock_calls[0],
        mx_acq.get_data_collection_group_params(),
        {
            "id": TEST_DATA_COLLECTION_GROUP_ID,
            "parentid": TEST_SESSION_ID,
            "experimenttype": "SAD",
            "sampleid": TEST_SAMPLE_ID,
            "sample_barcode": TEST_BARCODE,  # deferred
        },
    )
    assert_upsert_call_with(
        mx_acq.upsert_data_collection.mock_calls[0],
        mx_acq.get_data_collection_params(),
        {
            "id": TEST_DATA_COLLECTION_IDS[0],
            "visitid": TEST_SESSION_ID,
            "parentid": TEST_DATA_COLLECTION_GROUP_ID,
            "sampleid": TEST_SAMPLE_ID,
            "detectorid": 78,
            "axisstart": 0.0,
            "axisrange": 0.1,
            "axisend": 180,
            "focal_spot_size_at_samplex": 1.0,
            "focal_spot_size_at_sampley": 1.0,
            "slitgap_vertical": 1,
            "slitgap_horizontal": 1,
            "beamsize_at_samplex": 1,
            "beamsize_at_sampley": 1,
            "transmission": 100.0,
            "comments": "Hyperion rotation scan",
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
            "wavelength": 123.98419840550369,
            "xbeam": 150.0,
            "ybeam": 160.0,
            "xtal_snapshot1": "test_1_y",
            "xtal_snapshot2": "test_2_y",
            "xtal_snapshot3": "test_3_y",
            "synchrotron_mode": None,
            "starttime": EXPECTED_START_TIME,
            "filetemplate": "file_name_0_master.h5",
            "nimages": 1800,
            "kappastart": 0,
        },
    )

    assert_upsert_call_with(
        mx_acq.update_dc_position.mock_calls[0],
        mx_acq.get_dc_position_params(),
        {
            "id": TEST_DATA_COLLECTION_IDS[0],
            "pos_x": dummy_rotation_params.hyperion_params.ispyb_params.position[0],
            "pos_y": dummy_rotation_params.hyperion_params.ispyb_params.position[1],
            "pos_z": dummy_rotation_params.hyperion_params.ispyb_params.position[2],
        },
    )


@patch(
    "hyperion.external_interaction.ispyb.ispyb_store.get_current_time_string",
    return_value=EXPECTED_START_TIME,
)
def test_end_deposition_happy_path(
    get_current_time,
    ispyb_conn_with_2x2_collections_and_grid_info,
    dummy_rotation_ispyb,
    dummy_params,
):
    dummy_rotation_ispyb.begin_deposition()
    dummy_rotation_ispyb.update_deposition()
    mx_acq = mx_acquisition_from_conn(ispyb_conn_with_2x2_collections_and_grid_info)
    mx_acq.upsert_data_collection_group.reset_mock()
    mx_acq.upsert_data_collection.reset_mock()
    mx_acq.upsert_dc_grid.reset_mock()

    get_current_time.return_value = EXPECTED_END_TIME
    dummy_rotation_ispyb.end_deposition("success", "Test succeeded")
    assert mx_acq.update_data_collection_append_comments.call_args_list[0] == (
        (
            TEST_DATA_COLLECTION_IDS[0],
            "DataCollection Successful reason: Test succeeded",
            " ",
        ),
    )
    assert_upsert_call_with(
        mx_acq.upsert_data_collection.mock_calls[0],
        mx_acq.get_data_collection_params(),
        {
            "id": TEST_DATA_COLLECTION_IDS[0],
            "parentid": TEST_DATA_COLLECTION_GROUP_ID,
            "endtime": EXPECTED_END_TIME,
            "runstatus": "DataCollection Successful",
        },
    )
    assert len(mx_acq.upsert_data_collection.mock_calls) == 1


@patch("ispyb.open", new_callable=mock_open)
def test_store_rotation_scan_failures(
    ispyb_conn,
    dummy_rotation_ispyb: StoreRotationInIspyb,
    dummy_rotation_params: RotationInternalParameters,
):
    ispyb_conn.return_value.mx_acquisition = mock()
    ispyb_conn.return_value.core = mock()

    dummy_rotation_ispyb._data_collection_id = None

    with pytest.raises(AssertionError):
        dummy_rotation_ispyb.end_deposition("", "")

    with patch("hyperion.log.ISPYB_LOGGER.warning", autospec=True) as warning:
        dummy_rotation_params.hyperion_params.ispyb_params.xtal_snapshots_omega_start = (
            None
        )
        ispyb_no_snapshots = StoreRotationInIspyb(  # noqa
            SIM_ISPYB_CONFIG, dummy_rotation_params
        )
        warning.assert_called_once_with("No xtal snapshot paths sent to ISPyB!")


@pytest.mark.parametrize("dcgid", [2, 45, 61, 88, 13, 25])
@patch("ispyb.open", new_callable=mock_open)
def test_store_rotation_scan_uses_supplied_dcgid(
    ispyb_conn, dummy_rotation_params, dcgid
):
    ispyb_conn.return_value.mx_acquisition = MagicMock()
    ispyb_conn.return_value.core = mock()
    store_in_ispyb = StoreRotationInIspyb(
        SIM_ISPYB_CONFIG, dummy_rotation_params, dcgid
    )
    assert store_in_ispyb.begin_deposition().data_collection_group_id == dcgid
    assert store_in_ispyb.update_deposition().data_collection_group_id == dcgid


@patch("ispyb.open", new_callable=mock_open)
def test_mutate_params_rotation(
    ispyb_conn,
    dummy_rotation_ispyb: StoreRotationInIspyb,
    dummy_rotation_params: RotationInternalParameters,
):
    rotation_dict = deepcopy(EMPTY_DATA_COLLECTION_PARAMS)

    rotation_transformed = (
        dummy_rotation_ispyb._mutate_data_collection_params_for_experiment(
            rotation_dict
        )
    )
    assert rotation_transformed["axis_range"] == 0.1
    assert rotation_transformed["axis_end"] == 180.0
    assert rotation_transformed["n_images"] == 1800
