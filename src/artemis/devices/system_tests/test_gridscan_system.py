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
def test_set_program_data_and_kickoff(fast_grid_scan: FastGridScan):
    RE = RunEngine()
    RE(set_fast_grid_scan_params(fast_grid_scan, GridScanParams(2, 2)))
    kickoff_status = fast_grid_scan.kickoff()
    kickoff_status.wait()
