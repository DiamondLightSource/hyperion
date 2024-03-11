import os
from copy import deepcopy
from typing import Any, Callable, Sequence
from unittest.mock import MagicMock, mock_open, patch

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import pytest
from bluesky.run_engine import RunEngine
from ispyb.sp.mxacquisition import MXAcquisition
from ophyd.sim import SynAxis

from hyperion.external_interaction.callbacks.plan_reactive_callback import (
    PlanReactiveCallback,
)
from hyperion.parameters.external_parameters import from_file
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)
from hyperion.utils.utils import convert_angstrom_to_eV


class MockReactiveCallback(PlanReactiveCallback):
    activity_gated_start: MagicMock
    activity_gated_descriptor: MagicMock
    activity_gated_event: MagicMock
    activity_gated_stop: MagicMock

    def __init__(self, *, emit: Callable[..., Any] | None = None) -> None:
        super().__init__(MagicMock(), emit=emit)
        self.activity_gated_start = MagicMock(name="activity_gated_start")  # type: ignore
        self.activity_gated_descriptor = MagicMock(name="activity_gated_descriptor")  # type: ignore
        self.activity_gated_event = MagicMock(name="activity_gated_event")  # type: ignore
        self.activity_gated_stop = MagicMock(name="activity_gated_stop")  # type: ignore


@pytest.fixture
def mocked_test_callback():
    t = MockReactiveCallback()
    return t


@pytest.fixture
def RE_with_mock_callback(mocked_test_callback):
    RE = RunEngine()
    RE.subscribe(mocked_test_callback)
    yield RE, mocked_test_callback


def get_test_plan(callback_name):
    s = SynAxis(name="fake_signal")

    @bpp.run_decorator(md={"activate_callbacks": [callback_name]})
    def test_plan():
        yield from bps.create()
        yield from bps.read(s)
        yield from bps.save()

    return test_plan, s


@pytest.fixture
def test_rotation_params():
    param_dict = from_file(
        "tests/test_data/parameter_json_files/good_test_rotation_scan_parameters.json"
    )
    param_dict["hyperion_params"]["detector_params"]["directory"] = "tests/test_data"
    param_dict["hyperion_params"]["detector_params"]["prefix"] = "TEST_FILENAME"
    param_dict["hyperion_params"]["detector_params"]["current_energy_ev"] = 12700
    param_dict["hyperion_params"]["ispyb_params"]["current_energy_ev"] = 12700
    param_dict["experiment_params"]["rotation_angle"] = 360.0
    params = RotationInternalParameters(**param_dict)
    params.experiment_params.x = 0
    params.experiment_params.y = 0
    params.experiment_params.z = 0
    params.hyperion_params.detector_params.exposure_time = 0.004
    params.hyperion_params.ispyb_params.transmission_fraction = 0.49118047952
    return params


@pytest.fixture(params=[1044])
def test_fgs_params(request):
    params = GridscanInternalParameters(**default_raw_params())
    params.hyperion_params.ispyb_params.current_energy_ev = convert_angstrom_to_eV(1.0)
    params.hyperion_params.ispyb_params.flux = 9.0
    params.hyperion_params.ispyb_params.transmission_fraction = 0.5
    params.hyperion_params.detector_params.expected_energy_ev = convert_angstrom_to_eV(
        1.0
    )
    params.hyperion_params.detector_params.use_roi_mode = True
    params.hyperion_params.detector_params.num_triggers = request.param
    params.hyperion_params.detector_params.directory = (
        os.path.dirname(os.path.realpath(__file__)) + "/test_data"
    )
    params.hyperion_params.detector_params.prefix = "dummy"
    yield params


@pytest.fixture
def mock_ispyb_conn(base_ispyb_conn):
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


def mx_acquisition_from_conn(mock_ispyb_conn) -> MagicMock:
    return mock_ispyb_conn.return_value.__enter__.return_value.mx_acquisition


def assert_upsert_call_with(call, param_template, expected: dict):
    actual = remap_upsert_columns(list(param_template), call.args[0])
    assert actual == dict(param_template | expected)


TEST_DATA_COLLECTION_IDS = (12, 13)
TEST_DATA_COLLECTION_GROUP_ID = 34
TEST_GRID_INFO_IDS = (56, 57)
TEST_POSITION_ID = 78
TEST_SESSION_ID = 90
EXPECTED_START_TIME = "2024-02-08 14:03:59"
EXPECTED_END_TIME = "2024-02-08 14:04:01"


def remap_upsert_columns(keys: Sequence[str], values: list):
    return dict(zip(keys, values))


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

        def mock_retrieve_visit(visit_str):
            assert visit_str, "No visit id supplied"
            return TEST_SESSION_ID

        mock_core.retrieve_visit_id.side_effect = mock_retrieve_visit
        ispyb_connection.return_value.core = mock_core
        yield ispyb_connection


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


TEST_SAMPLE_ID = "0001"
TEST_BARCODE = "12345A"


def default_raw_params(
    json_file="tests/test_data/parameter_json_files/test_internal_parameter_defaults.json",
):
    return from_file(json_file)
