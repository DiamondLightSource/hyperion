from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from ispyb.sp.mxacquisition import MXAcquisition

from hyperion.external_interaction.callbacks.common.ispyb_mapping import (
    GridScanInfo,
    populate_data_collection_group,
    populate_remaining_data_collection_info,
)
from hyperion.external_interaction.callbacks.xray_centre.ispyb_mapping import (
    construct_comment_for_gridscan,
    populate_xy_data_collection_info,
)
from hyperion.external_interaction.ispyb.data_model import ScanDataInfo
from hyperion.external_interaction.ispyb.ispyb_store import (
    IspybIds,
    StoreInIspyb,
)
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)

from ..conftest import (
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
def ispyb_conn(base_ispyb_conn):
    return base_ispyb_conn


@pytest.fixture
def dummy_collection_group_info(dummy_params):
    return populate_data_collection_group(
        "mesh",
        dummy_params.hyperion_params.detector_params,
        dummy_params.hyperion_params.ispyb_params,
    )


@pytest.fixture
@patch(
    "hyperion.external_interaction.callbacks.common.ispyb_mapping.get_current_time_string",
    new=MagicMock(return_value=EXPECTED_START_TIME),
)
def scan_data_info_for_begin(dummy_params):
    grid_scan_info = GridScanInfo(
        dummy_params.hyperion_params.ispyb_params.upper_left,
        dummy_params.experiment_params.y_steps,
        dummy_params.experiment_params.y_step_size,
    )
    info = ScanDataInfo(
        data_collection_info=populate_remaining_data_collection_info(
            lambda: construct_comment_for_gridscan(
                dummy_params, dummy_params.hyperion_params.ispyb_params, grid_scan_info
            ),
            None,
            populate_xy_data_collection_info(
                grid_scan_info,
                dummy_params,
                dummy_params.hyperion_params.ispyb_params,
                dummy_params.hyperion_params.detector_params,
            ),
            dummy_params.hyperion_params.detector_params,
            dummy_params.hyperion_params.ispyb_params,
        ),
    )
    return info


def test_begin_deposition(
    mock_ispyb_conn,
    dummy_2d_gridscan_ispyb,
    dummy_params,
    dummy_collection_group_info,
    scan_data_info_for_begin,
):
    assert dummy_2d_gridscan_ispyb.begin_deposition(
        dummy_collection_group_info, scan_data_info_for_begin
    ) == IspybIds(
        data_collection_group_id=TEST_DATA_COLLECTION_GROUP_ID,
        data_collection_ids=(TEST_DATA_COLLECTION_IDS[0],),
    )

    mx_acq: MagicMock = mx_acquisition_from_conn(mock_ispyb_conn)
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
    mx_acq.upsert_data_collection.update_dc_position.assert_not_called()
    mx_acq.upsert_data_collection.update_dc_grid.assert_not_called()


@patch(
    "hyperion.external_interaction.callbacks.common.ispyb_mapping.get_current_time_string",
    new=MagicMock(return_value=EXPECTED_START_TIME),
)
def test_update_deposition(
    mock_ispyb_conn,
    dummy_2d_gridscan_ispyb,
    dummy_params,
    dummy_collection_group_info,
    scan_data_info_for_begin,
    scan_xy_data_info_for_update,
):
    ispyb_ids = dummy_2d_gridscan_ispyb.begin_deposition(
        dummy_collection_group_info, scan_data_info_for_begin
    )
    mx_acq = mx_acquisition_from_conn(mock_ispyb_conn)
    mx_acq.upsert_data_collection_group.assert_called_once()
    mx_acq.upsert_data_collection.assert_called_once()
    assert dummy_2d_gridscan_ispyb.update_deposition(
        ispyb_ids, dummy_collection_group_info, [scan_xy_data_info_for_update]
    ) == IspybIds(
        data_collection_group_id=TEST_DATA_COLLECTION_GROUP_ID,
        data_collection_ids=(TEST_DATA_COLLECTION_IDS[0],),
        grid_ids=(TEST_GRID_INFO_IDS[0],),
    )

    assert_upsert_call_with(
        mx_acq.upsert_data_collection_group.mock_calls[1],
        mx_acq.get_data_collection_group_params(),
        {
            "id": TEST_DATA_COLLECTION_GROUP_ID,
            "parentid": TEST_SESSION_ID,
            "experimenttype": "mesh",
            "sampleid": TEST_SAMPLE_ID,
            "sample_barcode": TEST_BARCODE,
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
    assert len(mx_acq.update_dc_position.mock_calls) == 1
    assert len(mx_acq.upsert_dc_grid.mock_calls) == 1
    assert len(mx_acq.upsert_data_collection.mock_calls) == 2
    assert len(mx_acq.upsert_data_collection_group.mock_calls) == 2


@patch(
    "hyperion.external_interaction.callbacks.common.ispyb_mapping.get_current_time_string",
    new=MagicMock(return_value=EXPECTED_START_TIME),
)
@patch("hyperion.external_interaction.ispyb.ispyb_store.get_current_time_string")
def test_end_deposition_happy_path(
    get_current_time,
    mock_ispyb_conn,
    dummy_2d_gridscan_ispyb,
    dummy_params,
    dummy_collection_group_info,
    scan_data_info_for_begin,
    scan_xy_data_info_for_update,
):
    ispyb_ids = dummy_2d_gridscan_ispyb.begin_deposition(
        dummy_collection_group_info, scan_data_info_for_begin
    )
    ispyb_ids = dummy_2d_gridscan_ispyb.update_deposition(
        ispyb_ids, dummy_collection_group_info, [scan_xy_data_info_for_update]
    )
    mx_acq: MagicMock = mx_acquisition_from_conn(mock_ispyb_conn)
    assert len(mx_acq.upsert_data_collection_group.mock_calls) == 2
    assert len(mx_acq.upsert_data_collection.mock_calls) == 2
    assert len(mx_acq.upsert_dc_grid.mock_calls) == 1

    get_current_time.return_value = EXPECTED_END_TIME
    dummy_2d_gridscan_ispyb.end_deposition(ispyb_ids, "success", "Test succeeded")
    assert mx_acq.update_data_collection_append_comments.call_args_list[0] == (
        (
            TEST_DATA_COLLECTION_IDS[0],
            "DataCollection Successful reason: Test succeeded",
            " ",
        ),
    )
    assert_upsert_call_with(
        mx_acq.upsert_data_collection.mock_calls[2],
        mx_acq.get_data_collection_params(),
        {
            "id": TEST_DATA_COLLECTION_IDS[0],
            "parentid": TEST_DATA_COLLECTION_GROUP_ID,
            "endtime": EXPECTED_END_TIME,
            "runstatus": "DataCollection Successful",
        },
    )
    assert len(mx_acq.upsert_data_collection.mock_calls) == 3


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
    mx_acquisition.upsert_dc_grid.return_value = TEST_GRID_INFO_IDS[0]


def test_param_keys(
    mock_ispyb_conn,
    dummy_2d_gridscan_ispyb,
    dummy_params,
    dummy_collection_group_info,
    scan_data_info_for_begin,
    scan_xy_data_info_for_update,
):
    ispyb_ids = dummy_2d_gridscan_ispyb.begin_deposition(
        dummy_collection_group_info, scan_data_info_for_begin
    )
    assert dummy_2d_gridscan_ispyb.update_deposition(
        ispyb_ids, dummy_collection_group_info, [scan_xy_data_info_for_update]
    ) == IspybIds(
        data_collection_ids=(TEST_DATA_COLLECTION_IDS[0],),
        data_collection_group_id=TEST_DATA_COLLECTION_GROUP_ID,
        grid_ids=(TEST_GRID_INFO_IDS[0],),
    )


def _test_when_grid_scan_stored_then_data_present_in_upserts(
    ispyb_conn,
    dummy_ispyb,
    test_function,
    dummy_collection_group_info,
    scan_data_info_for_begin,
    scan_data_info_for_update,
    test_group=False,
):
    setup_mock_return_values(ispyb_conn)
    ispyb_ids = dummy_ispyb.begin_deposition(
        dummy_collection_group_info, scan_data_info_for_begin
    )
    dummy_ispyb.update_deposition(
        ispyb_ids, dummy_collection_group_info, [scan_data_info_for_update]
    )

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
    ispyb_conn,
    dummy_2d_gridscan_ispyb,
    dummy_params,
    dummy_collection_group_info,
    scan_data_info_for_begin,
    scan_xy_data_info_for_update,
):
    dummy_params.hyperion_params.ispyb_params.sample_id = None
    dummy_collection_group_info.sample_id = None
    scan_data_info_for_begin.data_collection_info.sample_id = None
    scan_xy_data_info_for_update.data_collection_info.sample_id = None

    def test_sample_id(default_params, actual):
        sampleid_idx = list(default_params).index("sampleid")
        return actual[sampleid_idx] == default_params["sampleid"]

    _test_when_grid_scan_stored_then_data_present_in_upserts(
        ispyb_conn,
        dummy_2d_gridscan_ispyb,
        test_sample_id,
        dummy_collection_group_info,
        scan_data_info_for_begin,
        scan_xy_data_info_for_update,
        True,
    )


@patch("ispyb.open", autospec=True)
def test_given_real_sampleid_when_grid_scan_stored_then_sample_id_set(
    ispyb_conn,
    dummy_2d_gridscan_ispyb: StoreInIspyb,
    dummy_params: GridscanInternalParameters,
    dummy_collection_group_info,
    scan_data_info_for_begin,
    scan_xy_data_info_for_update,
):
    expected_sample_id = "0001"
    dummy_params.hyperion_params.ispyb_params.sample_id = expected_sample_id

    def test_sample_id(default_params, actual):
        sampleid_idx = list(default_params).index("sampleid")
        return actual[sampleid_idx] == expected_sample_id

    _test_when_grid_scan_stored_then_data_present_in_upserts(
        ispyb_conn,
        dummy_2d_gridscan_ispyb,
        test_sample_id,
        dummy_collection_group_info,
        scan_data_info_for_begin,
        scan_xy_data_info_for_update,
        True,
    )


def test_fail_result_run_results_in_bad_run_status(
    mock_ispyb_conn: MagicMock,
    dummy_2d_gridscan_ispyb: StoreInIspyb,
    dummy_params,
    dummy_collection_group_info,
    scan_data_info_for_begin,
    scan_xy_data_info_for_update,
):
    mock_ispyb_conn = mock_ispyb_conn
    mock_mx_aquisition = (
        mock_ispyb_conn.return_value.__enter__.return_value.mx_acquisition
    )
    mock_upsert_data_collection = mock_mx_aquisition.upsert_data_collection

    ispyb_ids = dummy_2d_gridscan_ispyb.begin_deposition(
        dummy_collection_group_info, scan_data_info_for_begin
    )
    ispyb_ids = dummy_2d_gridscan_ispyb.update_deposition(
        ispyb_ids, dummy_collection_group_info, [scan_xy_data_info_for_update]
    )
    dummy_2d_gridscan_ispyb.end_deposition(ispyb_ids, "fail", "test specifies failure")

    mock_upsert_data_collection_calls = mock_upsert_data_collection.call_args_list
    end_deposition_upsert_args = mock_upsert_data_collection_calls[2][0]
    upserted_param_value_list = end_deposition_upsert_args[0]
    assert "DataCollection Unsuccessful" in upserted_param_value_list
    assert "DataCollection Successful" not in upserted_param_value_list


def test_no_exception_during_run_results_in_good_run_status(
    mock_ispyb_conn: MagicMock,
    dummy_2d_gridscan_ispyb: StoreInIspyb,
    dummy_params,
    dummy_collection_group_info,
    scan_data_info_for_begin,
    scan_xy_data_info_for_update,
):
    mock_ispyb_conn = mock_ispyb_conn
    setup_mock_return_values(mock_ispyb_conn)
    mock_mx_aquisition = (
        mock_ispyb_conn.return_value.__enter__.return_value.mx_acquisition
    )
    mock_upsert_data_collection = mock_mx_aquisition.upsert_data_collection

    ispyb_ids = dummy_2d_gridscan_ispyb.begin_deposition(
        dummy_collection_group_info, scan_data_info_for_begin
    )
    ispyb_ids = dummy_2d_gridscan_ispyb.update_deposition(
        ispyb_ids, dummy_collection_group_info, [scan_xy_data_info_for_update]
    )
    dummy_2d_gridscan_ispyb.end_deposition(ispyb_ids, "success", "")

    mock_upsert_data_collection_calls = mock_upsert_data_collection.call_args_list
    end_deposition_upsert_args = mock_upsert_data_collection_calls[2][0]
    upserted_param_value_list = end_deposition_upsert_args[0]
    assert "DataCollection Unsuccessful" not in upserted_param_value_list
    assert "DataCollection Successful" in upserted_param_value_list


def test_ispyb_deposition_comment_correct(
    mock_ispyb_conn: MagicMock,
    dummy_2d_gridscan_ispyb: StoreInIspyb,
    dummy_params,
    dummy_collection_group_info,
    scan_data_info_for_begin,
    scan_xy_data_info_for_update,
):
    mock_mx_aquisition = mock_ispyb_conn.return_value.mx_acquisition
    mock_upsert_data_collection = mock_mx_aquisition.upsert_data_collection
    ispyb_ids = dummy_2d_gridscan_ispyb.begin_deposition(
        dummy_collection_group_info, scan_data_info_for_begin
    )
    dummy_2d_gridscan_ispyb.update_deposition(
        ispyb_ids, dummy_collection_group_info, [scan_xy_data_info_for_update]
    )
    mock_upsert_call_args = mock_upsert_data_collection.call_args_list[0][0]

    upserted_param_value_list = mock_upsert_call_args[0]
    assert upserted_param_value_list[29] == (
        "Hyperion: Xray centring - Diffraction grid scan of 40 by 20 images "
        "in 100.0 um by 100.0 um steps. Top left (px): [100,100], bottom right (px): [3300,1700]."
    )


@patch("ispyb.open", autospec=True)
def test_ispyb_deposition_rounds_position_to_int(
    mock_ispyb_conn: MagicMock,
    dummy_2d_gridscan_ispyb: StoreInIspyb,
    dummy_params,
    dummy_collection_group_info,
    scan_data_info_for_begin,
    scan_xy_data_info_for_update,
):
    dummy_params.hyperion_params.ispyb_params.upper_left = np.array([0.01, 100, 50])

    assert construct_comment_for_gridscan(
        dummy_params,
        dummy_params.hyperion_params.ispyb_params,
        GridScanInfo(dummy_params.hyperion_params.ispyb_params.upper_left, 20, 0.1),
    ) == (
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
    "hyperion.external_interaction.callbacks.xray_centre.ispyb_mapping.oav_utils.bottom_right_from_top_left",
    autospec=True,
)
def test_ispyb_deposition_rounds_box_size_int(
    bottom_right_from_top_left: MagicMock,
    dummy_2d_gridscan_ispyb: StoreInIspyb,
    dummy_params: GridscanInternalParameters,
    raw,
    rounded,
):
    dummy_params.experiment_params.x_steps = 0
    dummy_params.experiment_params.x_step_size = raw
    grid_scan_info = GridScanInfo(
        [
            0,
            0,
            0,
        ],
        0,
        raw,
    )
    bottom_right_from_top_left.return_value = grid_scan_info.upper_left

    assert construct_comment_for_gridscan(
        dummy_params, MagicMock(), grid_scan_info
    ) == (
        "Hyperion: Xray centring - Diffraction grid scan of 0 by 0 images in "
        f"{rounded} um by {rounded} um steps. Top left (px): [0,0], bottom right (px): [0,0]."
    )
