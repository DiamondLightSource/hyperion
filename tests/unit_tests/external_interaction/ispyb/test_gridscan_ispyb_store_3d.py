from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from mockito import when

from hyperion.external_interaction.ispyb.gridscan_ispyb_store_3d import (
    Store3DGridscanInIspyb,
)
from hyperion.external_interaction.ispyb.ispyb_store import IspybIds
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)
from unit_tests.external_interaction.ispyb.conftest import (
    TEST_BARCODE,
    TEST_DATA_COLLECTION_GROUP_ID,
    TEST_DATA_COLLECTION_IDS,
    TEST_GRID_INFO_IDS,
    TEST_POSITION_ID,
    TEST_SAMPLE_ID,
    TEST_SESSION_ID,
    assert_upsert_call_with,
    mx_acquisition_from_conn,
)

EXPECTED_START_TIME = "2024-02-08 14:03:59"
EXPECTED_END_TIME = "2024-02-08 14:04:01"


@pytest.fixture
def dummy_3d_gridscan_ispyb_with_hooks(dummy_3d_gridscan_ispyb):
    # Convenience hooks for asserting ispyb calls
    dummy_3d_gridscan_ispyb._upsert_data_collection_group = MagicMock(
        return_value=(TEST_DATA_COLLECTION_GROUP_ID)
    )
    dummy_3d_gridscan_ispyb._upsert_data_collection = MagicMock(
        return_value=TEST_DATA_COLLECTION_IDS[0]
    )
    return dummy_3d_gridscan_ispyb


def test_ispyb_deposition_comment_for_3D_correct(
    ispyb_conn_with_2x2_collections_and_grid_info: MagicMock,
    dummy_3d_gridscan_ispyb: Store3DGridscanInIspyb,
):
    mock_ispyb_conn = ispyb_conn_with_2x2_collections_and_grid_info
    mock_mx_aquisition = mx_acquisition_from_conn(mock_ispyb_conn)
    mock_upsert_dc = mock_mx_aquisition.upsert_data_collection
    dummy_3d_gridscan_ispyb.begin_deposition()
    dummy_3d_gridscan_ispyb.update_deposition()

    first_upserted_param_value_list = mock_upsert_dc.call_args_list[1][0][0]
    second_upserted_param_value_list = mock_upsert_dc.call_args_list[2][0][0]
    assert first_upserted_param_value_list[29] == (
        "Hyperion: Xray centring - Diffraction grid scan of 40 by 20 images "
        "in 100.0 um by 100.0 um steps. Top left (px): [100,100], bottom right (px): [3300,1700]."
    )
    assert second_upserted_param_value_list[29] == (
        "Hyperion: Xray centring - Diffraction grid scan of 40 by 10 images "
        "in 100.0 um by 100.0 um steps. Top left (px): [100,50], bottom right (px): [3300,850]."
    )


def test_store_3d_grid_scan(
    ispyb_conn_with_2x2_collections_and_grid_info,
    dummy_3d_gridscan_ispyb: Store3DGridscanInIspyb,
    dummy_params: GridscanInternalParameters,
):
    x = 0
    y = 1
    z = 2

    dummy_params.hyperion_params.ispyb_params.upper_left = np.array([x, y, z])
    dummy_params.experiment_params.z_step_size = 0.2

    assert dummy_3d_gridscan_ispyb.experiment_type == "Mesh3D"

    assert dummy_3d_gridscan_ispyb.begin_deposition() == IspybIds(
        data_collection_ids=(TEST_DATA_COLLECTION_IDS[0],),
        data_collection_group_id=TEST_DATA_COLLECTION_GROUP_ID,
    )

    assert dummy_3d_gridscan_ispyb.update_deposition() == IspybIds(
        data_collection_ids=TEST_DATA_COLLECTION_IDS,
        data_collection_group_id=TEST_DATA_COLLECTION_GROUP_ID,
        grid_ids=TEST_GRID_INFO_IDS,
    )

    assert (
        dummy_3d_gridscan_ispyb.omega_start
        == dummy_params.hyperion_params.detector_params.omega_start + 90
    )
    assert (
        dummy_3d_gridscan_ispyb.run_number
        == dummy_params.hyperion_params.detector_params.run_number + 1
    )
    assert (
        dummy_3d_gridscan_ispyb.xtal_snapshots
        == dummy_params.hyperion_params.ispyb_params.xtal_snapshots_omega_end
    )
    assert (
        dummy_3d_gridscan_ispyb.y_step_size
        == dummy_params.experiment_params.z_step_size
    )
    assert dummy_3d_gridscan_ispyb.y_steps == dummy_params.experiment_params.z_steps

    assert dummy_3d_gridscan_ispyb.upper_left is not None

    assert dummy_3d_gridscan_ispyb.upper_left[0] == x
    assert dummy_3d_gridscan_ispyb.upper_left[1] == z


def dict_to_ordered_params(param_template, kv_pairs: dict):
    param_template |= kv_pairs
    return list(param_template.values())


@patch(
    "hyperion.external_interaction.ispyb.ispyb_store.get_current_time_string",
    new=MagicMock(return_value=EXPECTED_START_TIME),
)
def test_begin_deposition(
    ispyb_conn_with_2x2_collections_and_grid_info,
    dummy_3d_gridscan_ispyb: Store3DGridscanInIspyb,
    dummy_params: GridscanInternalParameters,
):
    assert dummy_3d_gridscan_ispyb.begin_deposition() == IspybIds(
        data_collection_ids=(TEST_DATA_COLLECTION_IDS[0],),
        data_collection_group_id=TEST_DATA_COLLECTION_GROUP_ID,
    )

    mx_acq = mx_acquisition_from_conn(ispyb_conn_with_2x2_collections_and_grid_info)
    assert_upsert_call_with(
        mx_acq.upsert_data_collection_group.mock_calls[0],
        mx_acq.get_data_collection_group_params(),
        {
            "parentid": TEST_SESSION_ID,
            "experimenttype": "Mesh3D",
            "sampleid": TEST_SAMPLE_ID,
            "sample_barcode": TEST_BARCODE,  # deferred
        },
    )
    mx_acq.upsert_data_collection.assert_called_once()
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
            "images in 100.0 um by 100.0 um steps. Top left (px): [100,100], "
            "bottom right (px): [3300,1700].",
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
            "undulator_gap1": 1.0,
            "starttime": EXPECTED_START_TIME,
            "filetemplate": "file_name_0_master.h5",
            "nimages": 40 * 20,
        },
    )
    mx_acq.update_dc_position.assert_not_called()
    mx_acq.upsert_dc_grid.assert_not_called()


@patch(
    "hyperion.external_interaction.ispyb.ispyb_store.get_current_time_string",
    new=MagicMock(return_value=EXPECTED_START_TIME),
)
def test_update_deposition(
    ispyb_conn_with_2x2_collections_and_grid_info, dummy_3d_gridscan_ispyb, dummy_params
):
    y = 1
    x = 0
    z = 2

    dummy_params.hyperion_params.ispyb_params.upper_left = np.array([x, y, z])
    dummy_params.experiment_params.z_step_size = 0.2

    dummy_3d_gridscan_ispyb.begin_deposition()
    mx_acq = mx_acquisition_from_conn(ispyb_conn_with_2x2_collections_and_grid_info)
    mx_acq.upsert_data_collection_group.assert_called_once()
    mx_acq.upsert_data_collection.assert_called_once()

    actual_rows = dummy_3d_gridscan_ispyb.update_deposition()

    assert actual_rows == IspybIds(
        data_collection_group_id=TEST_DATA_COLLECTION_GROUP_ID,
        data_collection_ids=TEST_DATA_COLLECTION_IDS,
        grid_ids=TEST_GRID_INFO_IDS,
    )

    assert_upsert_call_with(
        mx_acq.upsert_data_collection_group.mock_calls[1],
        mx_acq.get_data_collection_group_params(),
        {
            "id": TEST_DATA_COLLECTION_GROUP_ID,
            "parentid": TEST_SESSION_ID,
            "experimenttype": "Mesh3D",
            "sampleid": TEST_SAMPLE_ID,
            "sample_barcode": TEST_BARCODE,  # deferred
        },
    )

    assert_upsert_call_with(
        mx_acq.upsert_data_collection.mock_calls[1],
        mx_acq.get_data_collection_params(),
        {
            "id": 12,
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
            "images in 100.0 um by 100.0 um steps. Top left (px): [0,1], "
            "bottom right (px): [3200,1601].",
            "data_collection_number": 0,
            "detector_distance": 100.0,
            "exp_time": 0.1,
            "imgdir": "/tmp/",
            "imgprefix": "file_name",
            "imgsuffix": "h5",
            "n_passes": 1,
            "overlap": 0,
            "flux": 10.0,
            "omegastart": 0.0,
            "start_image_number": 1,
            "resolution": 1.0,  # deferred
            "wavelength": 123.98419840550369,
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

    assert_upsert_call_with(
        mx_acq.update_dc_position.mock_calls[0],
        mx_acq.get_dc_position_params(),
        {
            "id": TEST_DATA_COLLECTION_IDS[0],
            "pos_x": dummy_params.hyperion_params.ispyb_params.position[0],
            "pos_y": dummy_params.hyperion_params.ispyb_params.position[1],
            "pos_z": dummy_params.hyperion_params.ispyb_params.position[2],
        },
    )

    assert_upsert_call_with(
        mx_acq.upsert_dc_grid.mock_calls[0],
        mx_acq.get_dc_grid_params(),
        {
            "parentid": TEST_DATA_COLLECTION_IDS[0],
            "dxinmm": dummy_params.experiment_params.x_step_size,
            "dyinmm": dummy_params.experiment_params.y_step_size,
            "stepsx": dummy_params.experiment_params.x_steps,
            "stepsy": dummy_params.experiment_params.y_steps,
            "micronsperpixelx": dummy_params.hyperion_params.ispyb_params.microns_per_pixel_x,
            "micronsperpixely": dummy_params.hyperion_params.ispyb_params.microns_per_pixel_y,
            "snapshotoffsetxpixel": dummy_params.hyperion_params.ispyb_params.upper_left[
                0
            ],
            "snapshotoffsetypixel": dummy_params.hyperion_params.ispyb_params.upper_left[
                1
            ],
            "orientation": "horizontal",
            "snaked": True,
        },
    )

    assert_upsert_call_with(
        mx_acq.upsert_data_collection.mock_calls[2],
        mx_acq.get_data_collection_params(),
        {
            "id": None,
            "visitid": TEST_SESSION_ID,
            "parentid": TEST_DATA_COLLECTION_GROUP_ID,
            "sampleid": TEST_SAMPLE_ID,
            "detectorid": 78,
            "axisstart": 90.0,
            "axisrange": 0,
            "axisend": 90.0,
            "focal_spot_size_at_samplex": 0.0,
            "focal_spot_size_at_sampley": 0.0,
            "slitgap_vertical": 0.1,
            "slitgap_horizontal": 0.1,
            "beamsize_at_samplex": 0.1,
            "beamsize_at_sampley": 0.1,
            "transmission": 100.0,
            "comments": "Hyperion: Xray centring - Diffraction grid scan of 40 by 10 "
            "images in 100.0 um by 200.0 um steps. Top left (px): [0,2], "
            "bottom right (px): [3200,1602].",
            "data_collection_number": 1,
            "detector_distance": 100.0,
            "exp_time": 0.1,
            "imgdir": "/tmp/",
            "imgprefix": "file_name",
            "imgsuffix": "h5",
            "n_passes": 1,
            "overlap": 0,
            "flux": 10.0,
            "omegastart": 90.0,
            "start_image_number": 1,
            "resolution": 1.0,  # deferred
            "wavelength": 123.98419840550369,
            "xbeam": 150.0,
            "ybeam": 160.0,
            "xtal_snapshot1": "test_1_z",
            "xtal_snapshot2": "test_2_z",
            "xtal_snapshot3": "test_3_z",
            "synchrotron_mode": None,
            "undulator_gap1": 1.0,
            "starttime": EXPECTED_START_TIME,
            "filetemplate": "file_name_1_master.h5",
            "nimages": 40 * 10,
        },
    )

    assert_upsert_call_with(
        mx_acq.update_dc_position.mock_calls[1],
        mx_acq.get_dc_position_params(),
        {
            "id": TEST_DATA_COLLECTION_IDS[1],
            "pos_x": dummy_params.hyperion_params.ispyb_params.position[0],
            "pos_y": dummy_params.hyperion_params.ispyb_params.position[1],
            "pos_z": dummy_params.hyperion_params.ispyb_params.position[2],
        },
    )

    assert_upsert_call_with(
        mx_acq.upsert_dc_grid.mock_calls[1],
        mx_acq.get_dc_grid_params(),
        {
            "parentid": TEST_DATA_COLLECTION_IDS[1],
            "dxinmm": dummy_params.experiment_params.x_step_size,
            "dyinmm": dummy_params.experiment_params.z_step_size,
            "stepsx": dummy_params.experiment_params.x_steps,
            "stepsy": dummy_params.experiment_params.z_steps,
            "micronsperpixelx": dummy_params.hyperion_params.ispyb_params.microns_per_pixel_x,
            "micronsperpixely": dummy_params.hyperion_params.ispyb_params.microns_per_pixel_y,
            "snapshotoffsetxpixel": dummy_params.hyperion_params.ispyb_params.upper_left[
                0
            ],
            "snapshotoffsetypixel": dummy_params.hyperion_params.ispyb_params.upper_left[
                2
            ],
            "orientation": "horizontal",
            "snaked": True,
        },
    )


@patch(
    "hyperion.external_interaction.ispyb.ispyb_store.get_current_time_string",
    return_value=EXPECTED_START_TIME,
)
def test_end_deposition_happy_path(
    get_current_time,
    ispyb_conn_with_2x2_collections_and_grid_info,
    dummy_3d_gridscan_ispyb,
    dummy_params,
):
    dummy_3d_gridscan_ispyb.begin_deposition()
    dummy_3d_gridscan_ispyb.update_deposition()
    mx_acq = mx_acquisition_from_conn(ispyb_conn_with_2x2_collections_and_grid_info)
    assert len(mx_acq.upsert_data_collection_group.mock_calls) == 2
    assert len(mx_acq.upsert_data_collection.mock_calls) == 3
    assert len(mx_acq.upsert_dc_grid.mock_calls) == 2

    get_current_time.return_value = EXPECTED_END_TIME
    dummy_3d_gridscan_ispyb.end_deposition("success", "Test succeeded")
    assert mx_acq.update_data_collection_append_comments.call_args_list[0] == (
        (
            TEST_DATA_COLLECTION_IDS[0],
            "DataCollection Successful reason: Test succeeded",
            " ",
        ),
    )
    assert_upsert_call_with(
        mx_acq.upsert_data_collection.mock_calls[3],
        mx_acq.get_data_collection_params(),
        {
            "id": TEST_DATA_COLLECTION_IDS[0],
            "parentid": TEST_DATA_COLLECTION_GROUP_ID,
            "endtime": EXPECTED_END_TIME,
            "runstatus": "DataCollection Successful",
        },
    )
    assert mx_acq.update_data_collection_append_comments.call_args_list[1] == (
        (
            TEST_DATA_COLLECTION_IDS[1],
            "DataCollection Successful reason: Test succeeded",
            " ",
        ),
    )
    assert_upsert_call_with(
        mx_acq.upsert_data_collection.mock_calls[4],
        mx_acq.get_data_collection_params(),
        {
            "id": TEST_DATA_COLLECTION_IDS[1],
            "parentid": TEST_DATA_COLLECTION_GROUP_ID,
            "endtime": EXPECTED_END_TIME,
            "runstatus": "DataCollection Successful",
        },
    )


def test_store_grid_scan(
    ispyb_conn_with_1_collection, dummy_2d_gridscan_ispyb, dummy_params
):
    ispyb_conn = ispyb_conn_with_1_collection
    when(dummy_2d_gridscan_ispyb)._store_position_table(
        ispyb_conn(), TEST_DATA_COLLECTION_IDS[0]
    ).thenReturn(TEST_POSITION_ID)
    when(dummy_2d_gridscan_ispyb)._store_grid_info_table(
        ispyb_conn(), TEST_DATA_COLLECTION_IDS[0]
    ).thenReturn(TEST_GRID_INFO_IDS[0])

    assert dummy_2d_gridscan_ispyb.experiment_type == "mesh"

    assert dummy_2d_gridscan_ispyb.begin_deposition() == IspybIds(
        data_collection_ids=(TEST_DATA_COLLECTION_IDS[0],),
        data_collection_group_id=TEST_DATA_COLLECTION_GROUP_ID,
    )
    assert dummy_2d_gridscan_ispyb._store_grid_scan(dummy_params) == (
        [TEST_DATA_COLLECTION_IDS[0]],
        [TEST_GRID_INFO_IDS[0]],
        TEST_DATA_COLLECTION_GROUP_ID,
    )
