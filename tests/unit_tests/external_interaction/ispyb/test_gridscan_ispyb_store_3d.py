from unittest.mock import MagicMock, patch

import pytest

from hyperion.external_interaction.ispyb.data_model import (
    DataCollectionGridInfo,
    DataCollectionGroupInfo,
    DataCollectionInfo,
    DataCollectionPositionInfo,
    ScanDataInfo,
)
from hyperion.external_interaction.ispyb.ispyb_dataclass import Orientation
from hyperion.external_interaction.ispyb.ispyb_store import (
    IspybIds,
    StoreInIspyb,
)

from ..conftest import (
    TEST_BARCODE,
    TEST_DATA_COLLECTION_GROUP_ID,
    TEST_DATA_COLLECTION_IDS,
    TEST_GRID_INFO_IDS,
    TEST_SAMPLE_ID,
    TEST_SESSION_ID,
    assert_upsert_call_with,
    mx_acquisition_from_conn,
)

EXPECTED_START_TIME = "2024-02-08 14:03:59"
EXPECTED_END_TIME = "2024-02-08 14:04:01"


@pytest.fixture
def dummy_collection_group_info():
    return DataCollectionGroupInfo(
        visit_string="cm31105-4",
        experiment_type="Mesh3D",
        sample_id="0001",
        sample_barcode="12345A",
    )


@pytest.fixture
def scan_data_info_for_begin():
    return ScanDataInfo(
        data_collection_info=DataCollectionInfo(
            omega_start=0.0,
            data_collection_number=0,
            xtal_snapshot1="test_1_y",
            xtal_snapshot2="test_2_y",
            xtal_snapshot3="test_3_y",
            n_images=800,
            axis_range=0,
            axis_end=0.0,
            kappa_start=None,
            parent_id=None,
            visit_string="cm31105-4",
            sample_id="0001",
            detector_id=78,
            axis_start=0.0,
            focal_spot_size_at_samplex=0.0,
            focal_spot_size_at_sampley=0.0,
            slitgap_vertical=0.1,
            slitgap_horizontal=0.1,
            beamsize_at_samplex=0.1,
            beamsize_at_sampley=0.1,
            transmission=100.0,
            comments="Hyperion: Xray centring - Diffraction grid scan of 40 by 20 images in 100.0 um by 100.0 um steps. Top left (px): [50,100], bottom right (px): [3250,1700].",
            detector_distance=100.0,
            exp_time=0.1,
            imgdir="/tmp/",
            file_template="file_name_0_master.h5",
            imgprefix="file_name",
            imgsuffix="h5",
            n_passes=1,
            overlap=0,
            start_image_number=1,
            resolution=1.0,
            wavelength=123.98419840550369,
            xbeam=150.0,
            ybeam=160.0,
            synchrotron_mode=None,
            undulator_gap1=1.0,
            start_time=EXPECTED_START_TIME,
        ),
        data_collection_id=None,
        data_collection_position_info=None,
        data_collection_grid_info=None,
    )


@pytest.fixture
def scan_data_infos_for_update():
    scan_xy_data_info_for_update = ScanDataInfo(
        data_collection_info=DataCollectionInfo(
            omega_start=0.0,
            data_collection_number=0,
            xtal_snapshot1="test_1_y",
            xtal_snapshot2="test_2_y",
            xtal_snapshot3="test_3_y",
            n_images=800,
            axis_range=0,
            axis_end=0.0,
            kappa_start=None,
            parent_id=34,
            visit_string="cm31105-4",
            sample_id="0001",
            detector_id=78,
            axis_start=0.0,
            focal_spot_size_at_samplex=0.0,
            focal_spot_size_at_sampley=0.0,
            slitgap_vertical=0.1,
            slitgap_horizontal=0.1,
            beamsize_at_samplex=0.1,
            beamsize_at_sampley=0.1,
            transmission=100.0,
            comments="Hyperion: Xray centring - Diffraction grid scan of 40 by 20 images in 100.0 um by 100.0 um steps. Top left (px): [50,100], bottom right (px): [3250,1700].",
            detector_distance=100.0,
            exp_time=0.1,
            imgdir="/tmp/",
            file_template="file_name_0_master.h5",
            imgprefix="file_name",
            imgsuffix="h5",
            n_passes=1,
            overlap=0,
            flux=10.0,
            start_image_number=1,
            resolution=1.0,
            wavelength=123.98419840550369,
            xbeam=150.0,
            ybeam=160.0,
            synchrotron_mode="test",
            undulator_gap1=1.0,
            start_time=EXPECTED_START_TIME,
        ),
        data_collection_id=None,
        data_collection_position_info=DataCollectionPositionInfo(
            pos_x=0, pos_y=0, pos_z=0
        ),
        data_collection_grid_info=DataCollectionGridInfo(
            dx_in_mm=0.1,
            dy_in_mm=0.1,
            steps_x=40,
            steps_y=20,
            microns_per_pixel_x=1.25,
            microns_per_pixel_y=1.25,
            snapshot_offset_x_pixel=50,
            snapshot_offset_y_pixel=100,
            orientation=Orientation.HORIZONTAL,
            snaked=True,
        ),
    )
    scan_xz_data_info_for_update = ScanDataInfo(
        data_collection_info=DataCollectionInfo(
            omega_start=90.0,
            data_collection_number=1,
            xtal_snapshot1="test_1_z",
            xtal_snapshot2="test_2_z",
            xtal_snapshot3="test_3_z",
            n_images=400,
            axis_range=0,
            axis_end=90.0,
            kappa_start=None,
            parent_id=34,
            visit_string="cm31105-4",
            sample_id="0001",
            detector_id=78,
            axis_start=90.0,
            focal_spot_size_at_samplex=0.0,
            focal_spot_size_at_sampley=0.0,
            slitgap_vertical=0.1,
            slitgap_horizontal=0.1,
            beamsize_at_samplex=0.1,
            beamsize_at_sampley=0.1,
            transmission=100.0,
            comments="Hyperion: Xray centring - Diffraction grid scan of 40 by 10 images in 100.0 um by 200.0 um steps. Top left (px): [50,120], bottom right (px): [3250,1720].",
            detector_distance=100.0,
            exp_time=0.1,
            imgdir="/tmp/",
            file_template="file_name_1_master.h5",
            imgprefix="file_name",
            imgsuffix="h5",
            n_passes=1,
            overlap=0,
            flux=10.0,
            start_image_number=1,
            resolution=1.0,
            wavelength=123.98419840550369,
            xbeam=150.0,
            ybeam=160.0,
            synchrotron_mode="test",
            undulator_gap1=1.0,
            start_time=EXPECTED_START_TIME,
        ),
        data_collection_id=None,
        data_collection_position_info=DataCollectionPositionInfo(
            pos_x=0.0, pos_y=0.0, pos_z=0.0
        ),
        data_collection_grid_info=DataCollectionGridInfo(
            dx_in_mm=0.1,
            dy_in_mm=0.2,
            steps_x=40,
            steps_y=10,
            microns_per_pixel_x=1.25,
            microns_per_pixel_y=1.25,
            snapshot_offset_x_pixel=50,
            snapshot_offset_y_pixel=120,
            orientation=Orientation.HORIZONTAL,
            snaked=True,
        ),
    )
    return [scan_xy_data_info_for_update, scan_xz_data_info_for_update]


def test_ispyb_deposition_comment_for_3D_correct(
    mock_ispyb_conn: MagicMock,
    dummy_3d_gridscan_ispyb: StoreInIspyb,
    dummy_collection_group_info,
    scan_data_info_for_begin,
    scan_data_infos_for_update,
):
    mock_ispyb_conn = mock_ispyb_conn
    mock_mx_aquisition = mx_acquisition_from_conn(mock_ispyb_conn)
    mock_upsert_dc = mock_mx_aquisition.upsert_data_collection
    ispyb_ids = dummy_3d_gridscan_ispyb.begin_deposition(
        dummy_collection_group_info, scan_data_info_for_begin
    )
    dummy_3d_gridscan_ispyb.update_deposition(
        ispyb_ids, dummy_collection_group_info, scan_data_infos_for_update
    )

    first_upserted_param_value_list = mock_upsert_dc.call_args_list[1][0][0]
    second_upserted_param_value_list = mock_upsert_dc.call_args_list[2][0][0]
    assert first_upserted_param_value_list[29] == (
        "Hyperion: Xray centring - Diffraction grid scan of 40 by 20 images "
        "in 100.0 um by 100.0 um steps. Top left (px): [50,100], bottom right (px): [3250,1700]."
    )
    assert second_upserted_param_value_list[29] == (
        "Hyperion: Xray centring - Diffraction grid scan of 40 by 10 images "
        "in 100.0 um by 200.0 um steps. Top left (px): [50,120], bottom right (px): [3250,1720]."
    )


def test_store_3d_grid_scan(
    mock_ispyb_conn,
    dummy_3d_gridscan_ispyb: StoreInIspyb,
    dummy_collection_group_info,
    scan_data_info_for_begin,
    scan_data_infos_for_update,
):
    assert dummy_3d_gridscan_ispyb.experiment_type == "Mesh3D"

    ispyb_ids = dummy_3d_gridscan_ispyb.begin_deposition(
        dummy_collection_group_info, scan_data_info_for_begin
    )
    assert ispyb_ids == IspybIds(
        data_collection_ids=(TEST_DATA_COLLECTION_IDS[0],),
        data_collection_group_id=TEST_DATA_COLLECTION_GROUP_ID,
    )

    assert dummy_3d_gridscan_ispyb.update_deposition(
        ispyb_ids, dummy_collection_group_info, scan_data_infos_for_update
    ) == IspybIds(
        data_collection_ids=TEST_DATA_COLLECTION_IDS,
        data_collection_group_id=TEST_DATA_COLLECTION_GROUP_ID,
        grid_ids=TEST_GRID_INFO_IDS,
    )


@patch(
    "hyperion.external_interaction.callbacks.common.ispyb_mapping.get_current_time_string",
    new=MagicMock(return_value=EXPECTED_START_TIME),
)
def test_begin_deposition(
    mock_ispyb_conn,
    dummy_3d_gridscan_ispyb: StoreInIspyb,
    dummy_collection_group_info,
    scan_data_info_for_begin,
):
    assert dummy_3d_gridscan_ispyb.begin_deposition(
        dummy_collection_group_info, scan_data_info_for_begin
    ) == IspybIds(
        data_collection_ids=(TEST_DATA_COLLECTION_IDS[0],),
        data_collection_group_id=TEST_DATA_COLLECTION_GROUP_ID,
    )

    mx_acq = mx_acquisition_from_conn(mock_ispyb_conn)
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
            "images in 100.0 um by 100.0 um steps. Top left (px): [50,100], "
            "bottom right (px): [3250,1700].",
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
    "hyperion.external_interaction.callbacks.common.ispyb_mapping.get_current_time_string",
    new=MagicMock(return_value=EXPECTED_START_TIME),
)
def test_update_deposition(
    mock_ispyb_conn,
    dummy_3d_gridscan_ispyb,
    dummy_collection_group_info,
    scan_data_info_for_begin,
    scan_data_infos_for_update,
):
    ispyb_ids = dummy_3d_gridscan_ispyb.begin_deposition(
        dummy_collection_group_info, scan_data_info_for_begin
    )
    mx_acq = mx_acquisition_from_conn(mock_ispyb_conn)
    mx_acq.upsert_data_collection_group.assert_called_once()
    mx_acq.upsert_data_collection.assert_called_once()

    actual_rows = dummy_3d_gridscan_ispyb.update_deposition(
        ispyb_ids, dummy_collection_group_info, scan_data_infos_for_update
    )

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
            "images in 100.0 um by 100.0 um steps. Top left (px): [50,100], "
            "bottom right (px): [3250,1700].",
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
            "synchrotron_mode": "test",
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
            "pos_x": 0,
            "pos_y": 0,
            "pos_z": 0,
        },
    )

    assert_upsert_call_with(
        mx_acq.upsert_dc_grid.mock_calls[0],
        mx_acq.get_dc_grid_params(),
        {
            "parentid": TEST_DATA_COLLECTION_IDS[0],
            "dxinmm": 0.1,
            "dyinmm": 0.1,
            "stepsx": 40,
            "stepsy": 20,
            "micronsperpixelx": 1.25,
            "micronsperpixely": 1.25,
            "snapshotoffsetxpixel": 50,
            "snapshotoffsetypixel": 100,
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
            "images in 100.0 um by 200.0 um steps. Top left (px): [50,120], "
            "bottom right (px): [3250,1720].",
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
            "synchrotron_mode": "test",
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
            "pos_x": 0,
            "pos_y": 0,
            "pos_z": 0,
        },
    )

    assert_upsert_call_with(
        mx_acq.upsert_dc_grid.mock_calls[1],
        mx_acq.get_dc_grid_params(),
        {
            "parentid": TEST_DATA_COLLECTION_IDS[1],
            "dxinmm": 0.1,
            "dyinmm": 0.2,
            "stepsx": 40,
            "stepsy": 10,
            "micronsperpixelx": 1.25,
            "micronsperpixely": 1.25,
            "snapshotoffsetxpixel": 50,
            "snapshotoffsetypixel": 120,
            "orientation": "horizontal",
            "snaked": True,
        },
    )


@patch(
    "hyperion.external_interaction.callbacks.common.ispyb_mapping.get_current_time_string",
    new=MagicMock(return_value=EXPECTED_START_TIME),
)
@patch(
    "hyperion.external_interaction.ispyb.ispyb_store.get_current_time_string",
)
def test_end_deposition_happy_path(
    get_current_time,
    mock_ispyb_conn,
    dummy_3d_gridscan_ispyb,
    dummy_collection_group_info,
    scan_data_info_for_begin,
    scan_data_infos_for_update,
):
    ispyb_ids = dummy_3d_gridscan_ispyb.begin_deposition(
        dummy_collection_group_info, scan_data_info_for_begin
    )
    ispyb_ids = dummy_3d_gridscan_ispyb.update_deposition(
        ispyb_ids, dummy_collection_group_info, scan_data_infos_for_update
    )
    mx_acq = mx_acquisition_from_conn(mock_ispyb_conn)
    assert len(mx_acq.upsert_data_collection_group.mock_calls) == 2
    assert len(mx_acq.upsert_data_collection.mock_calls) == 3
    assert len(mx_acq.upsert_dc_grid.mock_calls) == 2

    get_current_time.return_value = EXPECTED_END_TIME
    dummy_3d_gridscan_ispyb.end_deposition(ispyb_ids, "success", "Test succeeded")
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
