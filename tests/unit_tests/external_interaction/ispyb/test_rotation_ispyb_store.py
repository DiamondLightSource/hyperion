from unittest.mock import MagicMock, patch

import pytest

from hyperion.external_interaction.ispyb.data_model import (
    DataCollectionGroupInfo,
    DataCollectionInfo,
    DataCollectionPositionInfo,
    ExperimentType,
    ScanDataInfo,
)
from hyperion.external_interaction.ispyb.ispyb_store import (
    IspybIds,
    StoreInIspyb,
)
from hyperion.parameters.constants import CONST

from ..conftest import (
    EXPECTED_END_TIME,
    EXPECTED_START_TIME,
    TEST_BARCODE,
    TEST_DATA_COLLECTION_GROUP_ID,
    TEST_DATA_COLLECTION_IDS,
    TEST_SAMPLE_ID,
    TEST_SESSION_ID,
    assert_upsert_call_with,
    mx_acquisition_from_conn,
)

EXPECTED_DATA_COLLECTION = {
    "visitid": TEST_SESSION_ID,
    "parentid": TEST_DATA_COLLECTION_GROUP_ID,
    "sampleid": None,
    "detectorid": 78,
    "axisstart": 0.0,
    "axisrange": 0.1,
    "axisend": 180,
    "focal_spot_size_at_samplex": 1.0,
    "focal_spot_size_at_sampley": 1.0,
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
    "filetemplate": "file_name_1_master.h5",
    "nimages": 1800,
    "kappastart": 0,
}


@pytest.fixture
def dummy_rotation_data_collection_group_info():
    return DataCollectionGroupInfo(
        visit_string="cm31105-4",
        experiment_type="SAD",
        sample_id="364758",
    )


@pytest.fixture
@patch(
    "hyperion.external_interaction.callbacks.common.ispyb_mapping.get_current_time_string",
    new=MagicMock(return_value=EXPECTED_START_TIME),
)
def scan_data_info_for_begin():
    return ScanDataInfo(
        data_collection_info=DataCollectionInfo(
            omega_start=0.0,
            data_collection_number=0,
            xtal_snapshot1="test_1_y",
            xtal_snapshot2="test_2_y",
            xtal_snapshot3="test_3_y",
            n_images=1800,
            axis_range=0.1,
            axis_end=180.0,
            kappa_start=0.0,
            parent_id=None,
            visit_string="cm31105-4",
            sample_id="364758",
            detector_id=78,
            axis_start=0.0,
            focal_spot_size_at_samplex=1.0,
            focal_spot_size_at_sampley=1.0,
            beamsize_at_samplex=1.0,
            beamsize_at_sampley=1.0,
            transmission=100.0,
            comments="Hyperion rotation scan",
            detector_distance=100.0,
            exp_time=0.1,
            imgdir="/tmp/",
            file_template="file_name_1_master.h5",
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
            undulator_gap1=None,
            start_time="2024-02-08 14:03:59",
        ),
        data_collection_id=None,
        data_collection_position_info=None,
        data_collection_grid_info=None,
    )


@pytest.fixture
def scan_data_info_for_update(scan_data_info_for_begin):
    return ScanDataInfo(
        data_collection_info=DataCollectionInfo(
            omega_start=0.0,
            data_collection_number=0,
            xtal_snapshot1="test_1_y",
            xtal_snapshot2="test_2_y",
            xtal_snapshot3="test_3_y",
            n_images=1800,
            axis_range=0.1,
            axis_end=180.0,
            kappa_start=0.0,
            parent_id=None,
            visit_string="cm31105-4",
            detector_id=78,
            axis_start=0.0,
            focal_spot_size_at_samplex=1.0,
            focal_spot_size_at_sampley=1.0,
            slitgap_vertical=1.0,
            slitgap_horizontal=1.0,
            beamsize_at_samplex=1.0,
            beamsize_at_sampley=1.0,
            transmission=100.0,
            comments="Hyperion rotation scan",
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
            undulator_gap1=None,
            start_time="2024-02-08 14:03:59",
        ),
        data_collection_id=11,
        data_collection_position_info=DataCollectionPositionInfo(
            pos_x=10.0, pos_y=20.0, pos_z=30.0
        ),
        data_collection_grid_info=None,
    )


@pytest.fixture
def dummy_rotation_ispyb_with_experiment_type():
    store_in_ispyb = StoreInIspyb(
        CONST.SIM.ISPYB_CONFIG, ExperimentType.CHARACTERIZATION
    )
    return store_in_ispyb


@patch(
    "hyperion.external_interaction.callbacks.common.ispyb_mapping.get_current_time_string",
    new=MagicMock(return_value=EXPECTED_START_TIME),
)
def test_begin_deposition(
    mock_ispyb_conn,
    dummy_rotation_ispyb,
    dummy_rotation_data_collection_group_info,
    scan_data_info_for_begin,
):
    assert scan_data_info_for_begin.data_collection_info.parent_id is None

    assert dummy_rotation_ispyb.begin_deposition(
        dummy_rotation_data_collection_group_info, [scan_data_info_for_begin]
    ) == IspybIds(
        data_collection_ids=(TEST_DATA_COLLECTION_IDS[0],),
        data_collection_group_id=TEST_DATA_COLLECTION_GROUP_ID,
    )

    assert (
        scan_data_info_for_begin.data_collection_info.parent_id
        == TEST_DATA_COLLECTION_GROUP_ID
    )

    mx_acq = mx_acquisition_from_conn(mock_ispyb_conn)
    assert_upsert_call_with(
        mx_acq.upsert_data_collection_group.mock_calls[0],
        mx_acq.get_data_collection_group_params(),
        {
            "parentid": TEST_SESSION_ID,
            "experimenttype": "SAD",
            "sampleid": TEST_SAMPLE_ID,
        },
    )
    assert_upsert_call_with(
        mx_acq.upsert_data_collection.mock_calls[0],
        mx_acq.get_data_collection_params(),
        EXPECTED_DATA_COLLECTION | {"sampleid": TEST_SAMPLE_ID},
    )


@patch(
    "hyperion.external_interaction.callbacks.common.ispyb_mapping.get_current_time_string",
    new=MagicMock(return_value=EXPECTED_START_TIME),
)
def test_begin_deposition_with_group_id_updates_but_doesnt_insert(
    mock_ispyb_conn,
    dummy_rotation_data_collection_group_info,
    scan_data_info_for_begin,
):
    dummy_rotation_ispyb = StoreInIspyb(CONST.SIM.ISPYB_CONFIG, ExperimentType.ROTATION)
    scan_data_info_for_begin.data_collection_info.parent_id = (
        TEST_DATA_COLLECTION_GROUP_ID
    )

    assert dummy_rotation_ispyb.begin_deposition(
        dummy_rotation_data_collection_group_info, [scan_data_info_for_begin]
    ) == IspybIds(
        data_collection_ids=(TEST_DATA_COLLECTION_IDS[0],),
        data_collection_group_id=TEST_DATA_COLLECTION_GROUP_ID,
    )
    mx_acq = mx_acquisition_from_conn(mock_ispyb_conn)
    assert_upsert_call_with(
        mx_acq.upsert_data_collection_group.mock_calls[0],
        mx_acq.get_data_collection_group_params(),
        {
            "id": TEST_DATA_COLLECTION_GROUP_ID,
            "parentid": TEST_SESSION_ID,
            "experimenttype": "SAD",
            "sampleid": TEST_SAMPLE_ID,
        },
    )
    assert (
        scan_data_info_for_begin.data_collection_info.parent_id
        == TEST_DATA_COLLECTION_GROUP_ID
    )

    assert_upsert_call_with(
        mx_acq.upsert_data_collection.mock_calls[0],
        mx_acq.get_data_collection_params(),
        EXPECTED_DATA_COLLECTION | {"sampleid": TEST_SAMPLE_ID},
    )


@patch(
    "hyperion.external_interaction.callbacks.common.ispyb_mapping.get_current_time_string",
    new=MagicMock(return_value=EXPECTED_START_TIME),
)
def test_begin_deposition_with_alternate_experiment_type(
    mock_ispyb_conn,
    dummy_rotation_ispyb_with_experiment_type,
    dummy_rotation_data_collection_group_info,
    scan_data_info_for_begin,
):
    dummy_rotation_data_collection_group_info.experiment_type = "Characterization"
    assert dummy_rotation_ispyb_with_experiment_type.begin_deposition(
        dummy_rotation_data_collection_group_info,
        [scan_data_info_for_begin],
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
            "experimenttype": "Characterization",
            "sampleid": TEST_SAMPLE_ID,
        },
    )


@patch(
    "hyperion.external_interaction.ispyb.ispyb_store.get_current_time_string",
    new=MagicMock(return_value=EXPECTED_START_TIME),
)
def test_update_deposition(
    mock_ispyb_conn,
    dummy_rotation_ispyb,
    dummy_rotation_data_collection_group_info,
    scan_data_info_for_begin,
    scan_data_info_for_update,
):
    ispyb_ids = dummy_rotation_ispyb.begin_deposition(
        dummy_rotation_data_collection_group_info, [scan_data_info_for_begin]
    )
    mx_acq = mx_acquisition_from_conn(mock_ispyb_conn)
    mx_acq.upsert_data_collection_group.reset_mock()
    mx_acq.upsert_data_collection.reset_mock()

    scan_data_info_for_update.data_collection_info.parent_id = (
        ispyb_ids.data_collection_group_id
    )
    scan_data_info_for_update.data_collection_id = ispyb_ids.data_collection_ids[0]
    dummy_rotation_data_collection_group_info.sample_barcode = TEST_BARCODE

    assert dummy_rotation_ispyb.update_deposition(
        ispyb_ids,
        [scan_data_info_for_update],
    ) == IspybIds(
        data_collection_group_id=TEST_DATA_COLLECTION_GROUP_ID,
        data_collection_ids=(TEST_DATA_COLLECTION_IDS[0],),
    )
    mx_acq.upsert_data_collection_group.assert_not_called()
    assert_upsert_call_with(
        mx_acq.upsert_data_collection.mock_calls[0],
        mx_acq.get_data_collection_params(),
        EXPECTED_DATA_COLLECTION
        | {
            "id": TEST_DATA_COLLECTION_IDS[0],
            "synchrotron_mode": "test",
            "slitgap_vertical": 1,
            "slitgap_horizontal": 1,
            "flux": 10,
        },
    )

    assert_upsert_call_with(
        mx_acq.update_dc_position.mock_calls[0],
        mx_acq.get_dc_position_params(),
        {
            "id": TEST_DATA_COLLECTION_IDS[0],
            "pos_x": 10,
            "pos_y": 20,
            "pos_z": 30,
        },
    )


@patch(
    "hyperion.external_interaction.callbacks.common.ispyb_mapping.get_current_time_string",
    new=MagicMock(return_value=EXPECTED_START_TIME),
)
def test_update_deposition_with_group_id_updates(
    mock_ispyb_conn,
    dummy_rotation_data_collection_group_info,
    scan_data_info_for_begin,
    scan_data_info_for_update,
):
    dummy_rotation_ispyb = StoreInIspyb(CONST.SIM.ISPYB_CONFIG, ExperimentType.ROTATION)
    scan_data_info_for_begin.data_collection_info.parent_id = (
        TEST_DATA_COLLECTION_GROUP_ID
    )
    ispyb_ids = dummy_rotation_ispyb.begin_deposition(
        dummy_rotation_data_collection_group_info, [scan_data_info_for_begin]
    )
    mx_acq = mx_acquisition_from_conn(mock_ispyb_conn)
    mx_acq.upsert_data_collection_group.reset_mock()
    mx_acq.upsert_data_collection.reset_mock()

    scan_data_info_for_update.data_collection_info.parent_id = (
        ispyb_ids.data_collection_group_id
    )
    scan_data_info_for_update.data_collection_id = ispyb_ids.data_collection_ids[0]
    dummy_rotation_data_collection_group_info.sample_barcode = TEST_BARCODE
    assert dummy_rotation_ispyb.update_deposition(
        ispyb_ids,
        [scan_data_info_for_update],
    ) == IspybIds(
        data_collection_group_id=TEST_DATA_COLLECTION_GROUP_ID,
        data_collection_ids=(TEST_DATA_COLLECTION_IDS[0],),
    )
    mx_acq.upsert_data_collection_group.assert_not_called()
    assert_upsert_call_with(
        mx_acq.upsert_data_collection.mock_calls[0],
        mx_acq.get_data_collection_params(),
        EXPECTED_DATA_COLLECTION
        | {
            "id": TEST_DATA_COLLECTION_IDS[0],
            "synchrotron_mode": "test",
            "slitgap_vertical": 1,
            "slitgap_horizontal": 1,
            "flux": 10,
        },
    )

    assert_upsert_call_with(
        mx_acq.update_dc_position.mock_calls[0],
        mx_acq.get_dc_position_params(),
        {
            "id": TEST_DATA_COLLECTION_IDS[0],
            "pos_x": 10,
            "pos_y": 20,
            "pos_z": 30,
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
    dummy_rotation_ispyb,
    dummy_rotation_data_collection_group_info,
    scan_data_info_for_begin,
    scan_data_info_for_update,
):
    ispyb_ids = dummy_rotation_ispyb.begin_deposition(
        dummy_rotation_data_collection_group_info, [scan_data_info_for_begin]
    )
    scan_data_info_for_update.data_collection_info.parent_id = (
        ispyb_ids.data_collection_group_id
    )
    scan_data_info_for_update.data_collection_id = ispyb_ids.data_collection_ids[0]
    ispyb_ids = dummy_rotation_ispyb.update_deposition(
        ispyb_ids,
        [scan_data_info_for_update],
    )
    mx_acq = mx_acquisition_from_conn(mock_ispyb_conn)
    mx_acq.upsert_data_collection_group.reset_mock()
    mx_acq.upsert_data_collection.reset_mock()
    mx_acq.upsert_dc_grid.reset_mock()

    get_current_time.return_value = EXPECTED_END_TIME
    dummy_rotation_ispyb.end_deposition(ispyb_ids, "success", "Test succeeded")
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


def test_store_rotation_scan_failures(
    mock_ispyb_conn, dummy_rotation_ispyb: StoreInIspyb
):
    dummy_rotation_ispyb._data_collection_id = None

    ispyb_ids = IspybIds(
        data_collection_group_id=TEST_DATA_COLLECTION_GROUP_ID,
    )
    with pytest.raises(AssertionError):
        dummy_rotation_ispyb.end_deposition(ispyb_ids, "", "")


@pytest.mark.parametrize("dcgid", [2, 45, 61, 88, 13, 25])
def test_store_rotation_scan_uses_supplied_dcgid(
    mock_ispyb_conn,
    dcgid,
    dummy_rotation_data_collection_group_info,
    scan_data_info_for_begin,
    scan_data_info_for_update,
):
    mock_ispyb_conn.return_value.mx_acquisition.upsert_data_collection_group.return_value = (
        dcgid
    )
    store_in_ispyb = StoreInIspyb(CONST.SIM.ISPYB_CONFIG, ExperimentType.ROTATION)
    scan_data_info_for_begin.data_collection_info.parent_id = dcgid
    ispyb_ids = store_in_ispyb.begin_deposition(
        dummy_rotation_data_collection_group_info, [scan_data_info_for_begin]
    )
    assert ispyb_ids.data_collection_group_id == dcgid
    mx = mx_acquisition_from_conn(mock_ispyb_conn)
    assert_upsert_call_with(
        mx.upsert_data_collection_group.mock_calls[0],
        mx.get_data_collection_group_params(),
        {
            "id": dcgid,
            "parentid": TEST_SESSION_ID,
            "experimenttype": "SAD",
            "sampleid": TEST_SAMPLE_ID,
        },
    )
    assert (
        store_in_ispyb.update_deposition(
            ispyb_ids,
            [scan_data_info_for_update],
        ).data_collection_group_id
        == dcgid
    )
