import types
from unittest.mock import MagicMock, call, patch

from bluesky.run_engine import RunEngine
from dodal.devices.det_dim_constants import (
    EIGER2_X_4M_DIMENSION,
    EIGER_TYPE_EIGER2_X_4M,
    EIGER_TYPE_EIGER2_X_16M,
)
from dodal.devices.eiger import EigerDetector
from dodal.devices.fast_grid_scan import FastGridScan
from dodal.devices.motors import I03Smargon
from dodal.devices.slit_gaps import SlitGaps
from dodal.devices.synchrotron import Synchrotron
from dodal.devices.undulator import Undulator
from dodal.devices.zebra import Zebra
from mockito import ANY, when
from ophyd.sim import make_fake_device

from artemis.fast_grid_scan_plan import run_gridscan, update_params_from_epics_devices
from artemis.ispyb.store_in_ispyb import StoreInIspyb3D
from artemis.parameters import FullParameters

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


def test_when_run_gridscan_called_then_generator_returned():
    plan = run_gridscan(MagicMock(), MagicMock())
    assert isinstance(plan, types.GeneratorType)


def test_ispyb_params_update_from_ophyd_devices_correctly():
    RE = RunEngine({})
    params = FullParameters()

    undulator_test_value = 1.234
    FakeUndulator = make_fake_device(Undulator)
    undulator: Undulator = FakeUndulator(name="undulator")
    undulator.gap.user_readback.sim_put(undulator_test_value)

    synchrotron_test_value = "test"
    FakeSynchrotron = make_fake_device(Synchrotron)
    synchrotron: Synchrotron = FakeSynchrotron(name="synchrotron")
    synchrotron.machine_status.synchrotron_mode.sim_put(synchrotron_test_value)

    xgap_test_value = 0.1234
    ygap_test_value = 0.2345
    FakeSlitGaps = make_fake_device(SlitGaps)
    slit_gaps: SlitGaps = FakeSlitGaps(name="slit_gaps")
    slit_gaps.xgap.sim_put(xgap_test_value)
    slit_gaps.ygap.sim_put(ygap_test_value)

    RE(update_params_from_epics_devices(params, undulator, synchrotron, slit_gaps))

    assert params.ispyb_params.undulator_gap == undulator_test_value
    assert params.ispyb_params.synchrotron_mode == synchrotron_test_value
    assert params.ispyb_params.slit_gap_size_x == xgap_test_value
    assert params.ispyb_params.slit_gap_size_y == ygap_test_value


@patch("artemis.fast_grid_scan_plan.run_start")
@patch("artemis.fast_grid_scan_plan.run_end")
@patch("artemis.fast_grid_scan_plan.wait_for_result")
def test_run_gridscan_zocalo_calls(wait_for_result, run_end, run_start):
    dc_ids = [1, 2]
    dcg_id = 4

    params = FullParameters()
    params.grid_scan_params.z_steps = 2

    FakeFGS = make_fake_device(FastGridScan)
    fgs = FakeFGS(name="fgs")

    FakeZebra = make_fake_device(Zebra)
    zebra = FakeZebra(name="zebra")

    FakeUndulator = make_fake_device(Undulator)
    undulator = FakeUndulator(name="undulator")

    FakeSynchrotron = make_fake_device(Synchrotron)
    synchrotron = FakeSynchrotron(name="synchrotron")

    FakeSlitGaps = make_fake_device(SlitGaps)
    slit_gaps = FakeSlitGaps(name="slit_gaps")

    FakeSmargon = make_fake_device(I03Smargon)
    sample_motors = FakeSmargon(name="slit_gaps")

    FakeEiger = make_fake_device(EigerDetector)
    eiger: EigerDetector = FakeEiger(
        detector_params=params.detector_params, name="eiger"
    )

    when(StoreInIspyb3D).store_grid_scan(params).thenReturn([dc_ids, None, dcg_id])

    when(StoreInIspyb3D).get_current_time_string().thenReturn(DUMMY_TIME_STRING)

    when(StoreInIspyb3D).update_grid_scan_with_end_time_and_status(
        DUMMY_TIME_STRING, "DataCollection Successful", ANY(int), dcg_id
    )

    with patch("artemis.fast_grid_scan_plan.NexusWriter"):
        list(
            run_gridscan(
                fgs,
                zebra,
                undulator,
                synchrotron,
                slit_gaps,
                sample_motors,
                eiger,
                params,
            )
        )

    run_start.assert_has_calls(call(x) for x in dc_ids)
    assert run_start.call_count == len(dc_ids)

    run_end.assert_has_calls(call(x) for x in dc_ids)
    assert run_end.call_count == len(dc_ids)

    wait_for_result.assert_called_once_with(dcg_id)
