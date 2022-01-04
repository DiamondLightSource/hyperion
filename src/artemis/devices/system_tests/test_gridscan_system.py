import pytest

from src.artemis.devices.fast_grid_scan import FastGridScan


@pytest.fixture()
def fast_grid_scan():
    fast_grid_scan = FastGridScan(name="fast_grid_scan", prefix="BL03S-MO-SGON-01:FGS:")
    yield fast_grid_scan


@pytest.mark.s03
def test_set_program_data_and_kickoff(fast_grid_scan: FastGridScan):
    fast_grid_scan.set_program_data(2, 2, 0.1, 0.1, 1, 0, 0, 0)
    kickoff_status = fast_grid_scan.kickoff()
    kickoff_status.wait()
