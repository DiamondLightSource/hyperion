import types
from unittest.mock import call, patch

from bluesky.run_engine import RunEngine
from mockito import ANY, when
from ophyd.sim import make_fake_device
from src.artemis.devices.det_dim_constants import (
    EIGER2_X_4M_DIMENSION,
    EIGER_TYPE_EIGER2_X_4M,
    EIGER_TYPE_EIGER2_X_16M,
)
from src.artemis.devices.eiger import EigerDetector
from src.artemis.devices.fast_grid_scan import FastGridScan
from src.artemis.devices.motors import I03Smargon
from src.artemis.devices.undulator import Undulator
from src.artemis.devices.zebra import Zebra
from src.artemis.fast_grid_scan_plan import (
    get_plan,
    run_gridscan,
    update_params_from_epics_devices,
)
from src.artemis.ispyb.store_in_ispyb import StoreInIspyb3D
from src.artemis.parameters import FullParameters

DUMMY_TIME_STRING = "1970-01-01 00:00:00"


def test_given_full_parameters_dict_when_detector_name_used_and_converted_then_detector_constants_correct():
    params = FullParameters().to_dict()
    assert (
        params["detector_params"]["detector_size_constants"] == EIGER_TYPE_EIGER2_X_16M
    )
    params["detector_params"]["detector_size_constants"] = EIGER_TYPE_EIGER2_X_4M
    params: FullParameters = FullParameters.from_dict(params)
    det_dimension = params.detector_params.detector_size_constants.det_dimension
    assert det_dimension == EIGER2_X_4M_DIMENSION


def test_when_get_plan_called_then_generator_returned():
    plan = get_plan(FullParameters())
    assert isinstance(plan, types.GeneratorType)


def test_undulator_gap_updated_from_epics_device_correctly():
    RE = RunEngine({})
    test_value = 1.234
    params = FullParameters()
    FakeUndulator = make_fake_device(Undulator)
    undulator: Undulator = FakeUndulator(name="undulator")
    undulator.gap.user_readback.sim_put(test_value)
    RE(update_params_from_epics_devices(params, undulator))
    assert params.ispyb_params.undulator_gap == test_value


@patch("src.artemis.fast_grid_scan_plan.run_start")
@patch("src.artemis.fast_grid_scan_plan.run_end")
@patch("src.artemis.fast_grid_scan_plan.wait_for_result")
def test_run_gridscan_zocalo_calls(wait_for_result, run_end, run_start):
    dc_ids = [1, 2]
    dcg_id = 4

    params = FullParameters()
    params.grid_scan_params.z_steps = 2

    FakeUndulator = make_fake_device(Undulator)
    undulator: Undulator = FakeUndulator(name="undulator")

    FakeI03Smargon = make_fake_device(I03Smargon)
    motor_bundle: I03Smargon = FakeI03Smargon(name="motor_bundle")

    FakeEiger = make_fake_device(EigerDetector)
    eiger: EigerDetector = FakeEiger(
        detector_params=params.detector_params, name="eiger"
    )
    FakeZebra = make_fake_device(Zebra)
    zebra: Zebra = FakeZebra(name="zebra")
    FakeFGS = make_fake_device(FastGridScan)
    fast_grid_scan: FastGridScan = FakeFGS(name="fast_grid_scan")

    when(StoreInIspyb3D).store_grid_scan(params).thenReturn([dc_ids, None, dcg_id])

    when(StoreInIspyb3D).get_current_time_string().thenReturn(DUMMY_TIME_STRING)

    when(StoreInIspyb3D).update_grid_scan_with_end_time_and_status(
        DUMMY_TIME_STRING, "DataCollection Successful", ANY(int), dcg_id
    )

    with patch("src.artemis.fast_grid_scan_plan.NexusWriter"):
        list(
            run_gridscan(fast_grid_scan, zebra, eiger, motor_bundle, undulator, params)
        )

    run_start.assert_has_calls(call(x) for x in dc_ids)
    assert run_start.call_count == len(dc_ids)

    run_end.assert_has_calls(call(x) for x in dc_ids)
    assert run_end.call_count == len(dc_ids)

    wait_for_result.assert_called_once_with(dcg_id)
