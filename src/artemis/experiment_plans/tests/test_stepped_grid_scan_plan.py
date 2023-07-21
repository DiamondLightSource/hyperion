import bluesky.plan_stubs as bps
from artemis.experiment_plans import stepped_grid_scan_plan
from artemis.experiment_plans.stepped_grid_scan_plan import (
    run_gridscan,
    create_devices,
    stepped_grid_scan_composite,
    SteppedGridScanComposite,
    get_plan
)
import unittest.mock
from unittest.mock import MagicMock
import types
import functools
from bluesky import RunEngine


patch = functools.partial(unittest.mock.patch, autospec=True)


def test_when_run_stepped_grid_scan_called_then_generator_returned():
    plan = run_gridscan(MagicMock(), MagicMock())
    assert isinstance(plan, types.GeneratorType)


@patch("artemis.experiment_plans.stepped_grid_scan_plan.get_beamline_prefixes")
@patch("dodal.beamlines.i03.smargon")
def test_create_devices(smargon, get_beamline_prefixes):

    assert stepped_grid_scan_plan.stepped_grid_scan_composite is None
    create_devices()
    assert isinstance(stepped_grid_scan_plan.stepped_grid_scan_composite, SteppedGridScanComposite)

    get_beamline_prefixes.assert_called_once()
    smargon.assert_called_once()


@patch("bluesky.plan_stubs.abs_set")
@patch("artemis.experiment_plans.stepped_grid_scan_plan.grid_scan")
def test_run_plan_sets_omega_to_zero_and_then_calls_gridscan(grid_scan, abs_set, RE: RunEngine):
    sgs_composite: SteppedGridScanComposite = MagicMock()

    RE(run_gridscan(sgs_composite, MagicMock()))

    abs_set.assert_called_once_with(sgs_composite.sample_motors.omega, 0)
    grid_scan.assert_called_once()
