import functools
import types
import unittest.mock
from unittest.mock import MagicMock

from bluesky.run_engine import RunEngine

from hyperion.experiment_plans.stepped_grid_scan_plan import (
    SteppedGridScanComposite,
    run_gridscan,
)
from hyperion.parameters.plan_specific.stepped_grid_scan_internal_params import (
    SteppedGridScanInternalParameters,
)

patch = functools.partial(unittest.mock.patch, autospec=True)


def test_when_run_stepped_grid_scan_called_then_generator_returned():
    plan = run_gridscan(MagicMock(), MagicMock())
    assert isinstance(plan, types.GeneratorType)


@patch("bluesky.plan_stubs.abs_set")
@patch("bluesky.plans.grid_scan")
def test_run_plan_sets_omega_to_zero_and_then_calls_gridscan(
    grid_scan, abs_set, RE: RunEngine
):
    devices: SteppedGridScanComposite = SteppedGridScanComposite(
        smargon=MagicMock(),
    )
    RE(run_gridscan(devices, MagicMock(spec=SteppedGridScanInternalParameters)))

    abs_set.assert_called_once_with(devices.smargon.omega, 0)
    grid_scan.assert_called_once()
