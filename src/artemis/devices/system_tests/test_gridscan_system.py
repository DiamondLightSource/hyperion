import pytest

from src.artemis.devices.fast_grid_scan import (
    FastGridScan,
    set_fast_grid_scan_params,
    GridScanParams,
)
from bluesky.run_engine import RunEngine


@pytest.fixture()
def fast_grid_scan():
    fast_grid_scan = FastGridScan(name="fast_grid_scan", prefix="BL03S-MO-SGON-01:FGS:")
    yield fast_grid_scan


@pytest.mark.s03
def test_can_set_program_data_and_expected_images_correct(fast_grid_scan: FastGridScan):
    RE = RunEngine()
    RE(set_fast_grid_scan_params(fast_grid_scan, GridScanParams(2, 2)))
    assert fast_grid_scan.expected_images.get() == 2 * 2


@pytest.mark.s03
def test_staging_fast_grid_scan_clears_position_counter(fast_grid_scan: FastGridScan):
    RE = RunEngine()
    RE(set_fast_grid_scan_params(fast_grid_scan, GridScanParams(2, 2)))
    assert fast_grid_scan.expected_images.get() == 2 * 2
    fast_grid_scan.stage()
    assert fast_grid_scan.position_counter.get() == 0


@pytest.mark.s03
def test_given_valid_params_when_kickoff_then_completion_status_increases_and_finishes(
    fast_grid_scan: FastGridScan,
):
    prev_current, prev_fraction = None, None

    def progress_watcher(*args, **kwargs):
        nonlocal prev_current, prev_fraction
        if "current" in kwargs.keys() and "fraction" in kwargs.keys():
            current, fraction = kwargs["current"], kwargs["fraction"]
            if not prev_current:
                prev_current, prev_fraction = current, fraction
            else:
                assert current > prev_current
                assert fraction > prev_fraction
                assert 0 < fraction < 1
                assert 0 < prev_fraction < 1

    RE = RunEngine()
    RE(set_fast_grid_scan_params(fast_grid_scan, GridScanParams(3, 3)))
    fast_grid_scan.stage()
    assert fast_grid_scan.position_counter.get() == 0
    fast_grid_scan.kickoff()
    complete_status = fast_grid_scan.complete()
    complete_status.watch(progress_watcher)
    complete_status.wait()
    assert prev_current != None
    assert prev_fraction != None
