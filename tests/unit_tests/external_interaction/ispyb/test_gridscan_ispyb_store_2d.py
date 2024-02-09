from copy import deepcopy
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
from hyperion.external_interaction.ispyb.ispyb_store import (
    IspybIds,
)
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)

from .conftest import (
    TEST_DATA_COLLECTION_GROUP_ID,
    TEST_DATA_COLLECTION_IDS,
    TEST_GRID_INFO_ID,
    TEST_POSITION_ID,
    TEST_SESSION_ID,
)

EMPTY_DATA_COLLECTION_PARAMS = {
    "id": None,
    "parentid": None,
    "visitid": None,
    "sampleid": None,
    "detectorid": None,
    "positionid": None,
    "apertureid": None,
    "datacollectionnumber": None,
    "starttime": None,
    "endtime": None,
    "runstatus": None,
    "axisstart": None,
    "axisend": None,
    "axisrange": None,
    "overlap": None,
    "nimages": None,
    "startimagenumber": None,
    "npasses": None,
    "exptime": None,
    "imgdir": None,
    "imgprefix": None,
    "imgsuffix": None,
    "imgcontainersubpath": None,
    "filetemplate": None,
    "wavelength": None,
    "resolution": None,
    "detectordistance": None,
    "xbeam": None,
    "ybeam": None,
    "comments": None,
    "slitgapvertical": None,
    "slitgaphorizontal": None,
    "transmission_fraction": None,
    "synchrotronmode": None,
    "xtalsnapshot1": None,
    "xtalsnapshot2": None,
    "xtalsnapshot3": None,
    "xtalsnapshot4": None,
    "rotationaxis": None,
    "phistart": None,
    "kappastart": None,
    "omegastart": None,
    "resolutionatcorner": None,
    "detector2theta": None,
    "undulatorgap1": None,
    "undulatorgap2": None,
    "undulatorgap3": None,
    "beamsizeatsamplex": None,
    "beamsizeatsampley": None,
    "avgtemperature": None,
    "actualcenteringposition": None,
    "beamshape": None,
    "focalspotsizeatsamplex": None,
    "focalspotsizeatsampley": None,
    "polarisation": None,
    "flux": None,
    "processeddatafile": None,
    "datfile": None,
    "magnification": None,
    "totalabsorbeddose": None,
    "binning": None,
    "particlediameter": None,
    "boxsizectf": None,
    "minresolution": None,
    "mindefocus": None,
    "maxdefocus": None,
    "defocusstepsize": None,
    "amountastigmatism": None,
    "extractsize": None,
    "bgradius": None,
    "voltage": None,
    "objaperture": None,
    "c1aperture": None,
    "c2aperture": None,
    "c3aperture": None,
    "c1lens": None,
    "c2lens": None,
    "c3lens": None,
}


@pytest.fixture
def dummy_2d_gridscan_ispyb_with_hooks(dummy_2d_gridscan_ispyb):
    # Convenience hooks for asserting ispyb calls
    dummy_2d_gridscan_ispyb._upsert_data_collection_group = MagicMock(
        return_value=(TEST_DATA_COLLECTION_GROUP_ID)
    )
    dummy_2d_gridscan_ispyb._upsert_data_collection = MagicMock(
        return_value=TEST_DATA_COLLECTION_IDS[0]
    )
    return dummy_2d_gridscan_ispyb


@pytest.fixture
def ispyb_conn(base_ispyb_conn):
    return base_ispyb_conn


def test_begin_deposition(ispyb_conn, dummy_2d_gridscan_ispyb_with_hooks, dummy_params):
    assert dummy_2d_gridscan_ispyb_with_hooks.begin_deposition() == IspybIds(
        data_collection_group_id=TEST_DATA_COLLECTION_GROUP_ID,
        data_collection_ids=(TEST_DATA_COLLECTION_IDS[0],),
    )

    actual_params = (
        dummy_2d_gridscan_ispyb_with_hooks._upsert_data_collection_group.mock_calls[
            0
        ].args[1]
    )
    assert actual_params["parentid"] == TEST_SESSION_ID
    assert actual_params["experimenttype"] == "mesh"
    assert (
        actual_params["sampleid"] == dummy_params.hyperion_params.ispyb_params.sample_id
    )
    assert (
        actual_params["sample_barcode"]
        == dummy_params.hyperion_params.ispyb_params.sample_barcode
    )
    # TODO test collection data here also


def setup_mock_return_values(ispyb_conn):
    mx_acquisition = ispyb_conn.return_value.__enter__.return_value.mx_acquisition

    mx_acquisition.get_data_collection_group_params = (
        MXAcquisition.get_data_collection_group_params
    )
    mx_acquisition.get_data_collection_params = MXAcquisition.get_data_collection_params
    mx_acquisition.get_dc_grid_params = MXAcquisition.get_dc_grid_params
    mx_acquisition.get_dc_position_params = MXAcquisition.get_dc_position_params

    ispyb_conn.return_value.core.retrieve_visit_id.return_value = TEST_SESSION_ID
    mx_acquisition.upsert_data_collection.side_effect = TEST_DATA_COLLECTION_IDS * 2
    mx_acquisition.update_dc_position.return_value = TEST_POSITION_ID
    mx_acquisition.upsert_data_collection_group.return_value = (
        TEST_DATA_COLLECTION_GROUP_ID
    )
    mx_acquisition.upsert_dc_grid.return_value = TEST_GRID_INFO_ID


def test_param_keys(
    ispyb_conn_with_2x2_collections_and_grid_info, dummy_2d_gridscan_ispyb, dummy_params
):
    dummy_2d_gridscan_ispyb.begin_deposition()
    assert dummy_2d_gridscan_ispyb._store_grid_scan(dummy_params) == (
        [TEST_DATA_COLLECTION_IDS[0]],
        [TEST_GRID_INFO_ID],
        TEST_DATA_COLLECTION_GROUP_ID,
    )


def _test_when_grid_scan_stored_then_data_present_in_upserts(
    ispyb_conn, dummy_ispyb, dummy_params, test_function, test_group=False
):
    setup_mock_return_values(ispyb_conn)
    dummy_ispyb.begin_deposition()
    dummy_ispyb._store_grid_scan(dummy_params)

    mx_acquisition = ispyb_conn.return_value.__enter__.return_value.mx_acquisition

    upsert_data_collection_arg_list = (
        mx_acquisition.upsert_data_collection.call_args_list[1][0]
    )
    actual = upsert_data_collection_arg_list[0]
    assert test_function(MXAcquisition.get_data_collection_params(), actual)

    if test_group:
        upsert_data_collection_group_arg_list = (
            mx_acquisition.upsert_data_collection_group.call_args_list[1][0]
        )
        actual = upsert_data_collection_group_arg_list[0]
        assert test_function(MXAcquisition.get_data_collection_group_params(), actual)


@patch("ispyb.open", autospec=True)
def test_given_sampleid_of_none_when_grid_scan_stored_then_sample_id_not_set(
    ispyb_conn, dummy_2d_gridscan_ispyb, dummy_params
):
    dummy_params.hyperion_params.ispyb_params.sample_id = None

    def test_sample_id(default_params, actual):
        sampleid_idx = list(default_params).index("sampleid")
        return actual[sampleid_idx] == default_params["sampleid"]

    _test_when_grid_scan_stored_then_data_present_in_upserts(
        ispyb_conn, dummy_2d_gridscan_ispyb, dummy_params, test_sample_id, True
    )


@patch("ispyb.open", autospec=True)
def test_given_real_sampleid_when_grid_scan_stored_then_sample_id_set(
    ispyb_conn,
    dummy_2d_gridscan_ispyb: Store2DGridscanInIspyb,
    dummy_params: GridscanInternalParameters,
):
    expected_sample_id = "0001"
    dummy_params.hyperion_params.ispyb_params.sample_id = expected_sample_id

    def test_sample_id(default_params, actual):
        sampleid_idx = list(default_params).index("sampleid")
        return actual[sampleid_idx] == expected_sample_id

    _test_when_grid_scan_stored_then_data_present_in_upserts(
        ispyb_conn, dummy_2d_gridscan_ispyb, dummy_params, test_sample_id, True
    )


def test_fail_result_run_results_in_bad_run_status(
    ispyb_conn_with_2x2_collections_and_grid_info: MagicMock,
    dummy_2d_gridscan_ispyb: Store2DGridscanInIspyb,
):
    mock_ispyb_conn = ispyb_conn_with_2x2_collections_and_grid_info
    mock_mx_aquisition = (
        mock_ispyb_conn.return_value.__enter__.return_value.mx_acquisition
    )
    mock_upsert_data_collection = mock_mx_aquisition.upsert_data_collection

    dummy_2d_gridscan_ispyb.begin_deposition()
    dummy_2d_gridscan_ispyb.update_deposition()
    dummy_2d_gridscan_ispyb.end_deposition("fail", "test specifies failure")

    mock_upsert_data_collection_calls = mock_upsert_data_collection.call_args_list
    end_deposition_upsert_args = mock_upsert_data_collection_calls[2][0]
    upserted_param_value_list = end_deposition_upsert_args[0]
    assert "DataCollection Unsuccessful" in upserted_param_value_list
    assert "DataCollection Successful" not in upserted_param_value_list


def test_no_exception_during_run_results_in_good_run_status(
    ispyb_conn_with_2x2_collections_and_grid_info: MagicMock,
    dummy_2d_gridscan_ispyb: Store2DGridscanInIspyb,
):
    mock_ispyb_conn = ispyb_conn_with_2x2_collections_and_grid_info
    setup_mock_return_values(mock_ispyb_conn)
    mock_mx_aquisition = (
        mock_ispyb_conn.return_value.__enter__.return_value.mx_acquisition
    )
    mock_upsert_data_collection = mock_mx_aquisition.upsert_data_collection

    dummy_2d_gridscan_ispyb.begin_deposition()
    dummy_2d_gridscan_ispyb.update_deposition()
    dummy_2d_gridscan_ispyb.end_deposition("success", "")

    mock_upsert_data_collection_calls = mock_upsert_data_collection.call_args_list
    end_deposition_upsert_args = mock_upsert_data_collection_calls[2][0]
    upserted_param_value_list = end_deposition_upsert_args[0]
    assert "DataCollection Unsuccessful" not in upserted_param_value_list
    assert "DataCollection Successful" in upserted_param_value_list


def test_ispyb_deposition_comment_correct(
    ispyb_conn_with_2x2_collections_and_grid_info: MagicMock,
    dummy_2d_gridscan_ispyb: Store2DGridscanInIspyb,
):
    mock_mx_aquisition = (
        ispyb_conn_with_2x2_collections_and_grid_info.return_value.mx_acquisition
    )
    mock_upsert_data_collection = mock_mx_aquisition.upsert_data_collection
    dummy_2d_gridscan_ispyb.begin_deposition()
    dummy_2d_gridscan_ispyb.update_deposition()
    mock_upsert_call_args = mock_upsert_data_collection.call_args_list[0][0]

    upserted_param_value_list = mock_upsert_call_args[0]
    assert upserted_param_value_list[29] == (
        "Hyperion: Xray centring - Diffraction grid scan of 40 by 20 images "
        "in 100.0 um by 100.0 um steps. Top left (px): [100,100], bottom right (px): [3300,1700]."
    )


@patch("ispyb.open", autospec=True)
def test_ispyb_deposition_rounds_position_to_int(
    mock_ispyb_conn: MagicMock,
    dummy_2d_gridscan_ispyb: Store2DGridscanInIspyb,
):
    setup_mock_return_values(mock_ispyb_conn)
    mock_mx_aquisition = (
        mock_ispyb_conn.return_value.__enter__.return_value.mx_acquisition
    )
    mock_upsert_data_collection = mock_mx_aquisition.upsert_data_collection
    assert dummy_2d_gridscan_ispyb.full_params is not None
    dummy_2d_gridscan_ispyb.full_params.hyperion_params.ispyb_params.upper_left = (
        np.array([0.01, 100, 50])
    )
    dummy_2d_gridscan_ispyb.begin_deposition()
    dummy_2d_gridscan_ispyb.update_deposition()
    mock_upsert_call_args = mock_upsert_data_collection.call_args_list[1][0]

    upserted_param_value_list = mock_upsert_call_args[0]
    assert upserted_param_value_list[29] == (
        "Hyperion: Xray centring - Diffraction grid scan of 40 by 20 images "
        "in 100.0 um by 100.0 um steps. Top left (px): [0,100], bottom right (px): [3200,1700]."
    )


@pytest.mark.parametrize(
    ["raw", "rounded"],
    [
        (0.0012345, "1.2"),
        (0.020000000, "20.0"),
        (0.01999999, "20.0"),
        (0.015257, "15.3"),
        (0.0001234, "0.1"),
        (0.0017345, "1.7"),
        (0.0019945, "2.0"),
    ],
)
@patch(
    "hyperion.external_interaction.ispyb.gridscan_ispyb_store.oav_utils.bottom_right_from_top_left",
    autospec=True,
)
def test_ispyb_deposition_rounds_box_size_int(
    bottom_right_from_top_left: MagicMock,
    dummy_2d_gridscan_ispyb: Store2DGridscanInIspyb,
    dummy_params: GridscanInternalParameters,
    raw,
    rounded,
):
    bottom_right_from_top_left.return_value = dummy_2d_gridscan_ispyb.upper_left = [
        0,
        0,
        0,
    ]
    dummy_2d_gridscan_ispyb.ispyb_params = MagicMock()
    dummy_2d_gridscan_ispyb.full_params = dummy_params
    dummy_2d_gridscan_ispyb.y_steps = (
        dummy_2d_gridscan_ispyb.full_params.experiment_params.x_steps
    ) = 0

    dummy_2d_gridscan_ispyb.y_step_size = (
        dummy_2d_gridscan_ispyb.full_params.experiment_params.x_step_size
    ) = raw

    assert dummy_2d_gridscan_ispyb._construct_comment() == (
        "Hyperion: Xray centring - Diffraction grid scan of 0 by 0 images in "
        f"{rounded} um by {rounded} um steps. Top left (px): [0,0], bottom right (px): [0,0]."
    )


@patch("ispyb.open", autospec=True)
def test_given_x_and_y_steps_different_from_total_images_when_grid_scan_stored_then_num_images_correct(
    ispyb_conn,
    dummy_2d_gridscan_ispyb: Store2DGridscanInIspyb,
    dummy_params: GridscanInternalParameters,
):
    expected_number_of_steps = 200 * 3
    dummy_params.experiment_params.x_steps = 200
    dummy_params.experiment_params.y_steps = 3

    def test_number_of_steps(default_params, actual):
        # Note that internally the ispyb API removes underscores so this is the same as n_images
        number_of_steps_idx = list(default_params).index("nimages")
        return actual[number_of_steps_idx] == expected_number_of_steps

    _test_when_grid_scan_stored_then_data_present_in_upserts(
        ispyb_conn, dummy_2d_gridscan_ispyb, dummy_params, test_number_of_steps
    )


@patch("ispyb.open", new_callable=mock_open)
def test_mutate_params_gridscan(
    ispyb_conn,
    dummy_3d_gridscan_ispyb: Store3DGridscanInIspyb,
    dummy_params: GridscanInternalParameters,
):
    fgs_dict = deepcopy(EMPTY_DATA_COLLECTION_PARAMS)

    dummy_3d_gridscan_ispyb.y_steps = 5

    fgs_transformed = (
        dummy_3d_gridscan_ispyb._mutate_data_collection_params_for_experiment(fgs_dict)
    )
    assert fgs_transformed["axis_range"] == 0
    assert fgs_transformed["n_images"] == 200
