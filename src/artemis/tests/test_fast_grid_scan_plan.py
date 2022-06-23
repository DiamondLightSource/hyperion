import types

from bluesky.run_engine import RunEngine
from ophyd.sim import make_fake_device
from src.artemis.devices.det_dim_constants import (EIGER2_X_4M_DIMENSION,
                                                   EIGER_TYPE_EIGER2_X_4M,
                                                   EIGER_TYPE_EIGER2_X_16M)
from src.artemis.devices.undulator import Undulator
from src.artemis.fast_grid_scan_plan import (get_plan,
                                             update_params_from_epics_devices)
from src.artemis.parameters import FullParameters


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


def test_parameters_updated_from_epics_devices_correctly():
    RE = RunEngine({})
    test_value = 1.234
    params = FullParameters()
    FakeUndulator = make_fake_device(Undulator)
    undulator: Undulator = FakeUndulator(name="undulator")
    undulator.gap.user_readback.sim_put(test_value)
    RE(update_params_from_epics_devices(params, undulator))
    assert params.ispyb_params.undulator_gap == test_value
