from copy import deepcopy
from unittest.mock import MagicMock, mock_open, patch

import pytest
from mockito import mock, when

from hyperion.external_interaction.ispyb.ispyb_store import IspybIds
from hyperion.external_interaction.ispyb.rotation_ispyb_store import (
    StoreRotationInIspyb,
)
from hyperion.parameters.constants import SIM_ISPYB_CONFIG
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)
from unit_tests.external_interaction.ispyb.conftest import (
    TEST_DATA_COLLECTION_GROUP_ID,
    TEST_DATA_COLLECTION_IDS,
    TEST_POSITION_ID,
)
from unit_tests.external_interaction.ispyb.test_gridscan_ispyb_store_2d import (
    EMPTY_DATA_COLLECTION_PARAMS,
)


@patch("ispyb.open", new_callable=mock_open)
def test_store_rotation_scan_failures(
    ispyb_conn,
    dummy_rotation_ispyb: StoreRotationInIspyb,
    dummy_rotation_params: RotationInternalParameters,
):
    ispyb_conn.return_value.mx_acquisition = mock()
    ispyb_conn.return_value.core = mock()

    dummy_rotation_ispyb.data_collection_id = None

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
def test_store_rotation_scan(
    ispyb_conn, dummy_rotation_ispyb: StoreRotationInIspyb, dummy_rotation_params
):
    ispyb_conn.return_value.mx_acquisition = mock()
    ispyb_conn.return_value.core = mock()

    when(dummy_rotation_ispyb)._store_position_table(
        ispyb_conn(), TEST_DATA_COLLECTION_IDS[0]
    ).thenReturn(TEST_POSITION_ID)

    when(dummy_rotation_ispyb)._store_data_collection_group_table(
        ispyb_conn()
    ).thenReturn(TEST_DATA_COLLECTION_GROUP_ID)

    when(dummy_rotation_ispyb)._store_data_collection_table(
        ispyb_conn(), TEST_DATA_COLLECTION_GROUP_ID
    ).thenReturn(TEST_DATA_COLLECTION_IDS[0])

    assert dummy_rotation_ispyb.experiment_type == "SAD"

    assert dummy_rotation_ispyb.begin_deposition() == IspybIds(
        data_collection_ids=TEST_DATA_COLLECTION_IDS[0],
        data_collection_group_id=TEST_DATA_COLLECTION_GROUP_ID,
    )

    assert dummy_rotation_ispyb._store_scan_data(ispyb_conn()) == (
        TEST_DATA_COLLECTION_IDS[0],
        TEST_DATA_COLLECTION_GROUP_ID,
    )

    assert dummy_rotation_ispyb.update_deposition() == IspybIds(
        data_collection_ids=TEST_DATA_COLLECTION_IDS[0],
        data_collection_group_id=TEST_DATA_COLLECTION_GROUP_ID,
    )


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
