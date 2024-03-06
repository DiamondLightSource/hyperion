import os
from typing import Any, Callable
from unittest.mock import MagicMock

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import pytest
from bluesky.run_engine import RunEngine
from ophyd.sim import SynAxis

from hyperion.external_interaction.callbacks.plan_reactive_callback import (
    PlanReactiveCallback,
)
from hyperion.parameters.external_parameters import from_file
from hyperion.parameters.external_parameters import from_file as default_raw_params
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
