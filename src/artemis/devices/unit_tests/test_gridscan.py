from ophyd.sim import make_fake_device
from src.artemis.devices.fast_grid_scan import FastGridScan, time

from mockito import *
from mockito.matchers import *
import pytest


@pytest.fixture
def fast_grid_scan():
    FakeFastGridScan = make_fake_device(FastGridScan)
    fast_grid_scan: FastGridScan = FakeFastGridScan(name="test")
    fast_grid_scan.scan_invalid.pvname = ""

    # A bit of a hack to assume that if we are waiting on something then we will timeout
    when(time).sleep(ANY).thenRaise(TimeoutError())
    return fast_grid_scan


def test_given_invalid_scan_when_kickoff_then_timeout(fast_grid_scan: FastGridScan):
    when(fast_grid_scan.scan_invalid).get().thenReturn(True)
    when(fast_grid_scan.position_counter).get().thenReturn(0)

    status = fast_grid_scan.kickoff()

    with pytest.raises(TimeoutError):
        status.wait()


def test_given_image_counter_not_reset_when_kickoff_then_timeout(
    fast_grid_scan: FastGridScan,
):
    when(fast_grid_scan.scan_invalid).get().thenReturn(False)
    when(fast_grid_scan.position_counter).get().thenReturn(10)

    status = fast_grid_scan.kickoff()

    with pytest.raises(TimeoutError):
        status.wait()


def test_given_settings_valid_when_kickoff_then_run_started(
    fast_grid_scan: FastGridScan,
):
    when(fast_grid_scan.scan_invalid).get().thenReturn(False)
    when(fast_grid_scan.position_counter).get().thenReturn(0)

    mock_run_set_status = mock()
    when(fast_grid_scan.run_cmd).set(ANY).thenReturn(mock_run_set_status)
    fast_grid_scan.status.subscribe = lambda func, **kwargs: func(1)

    status = fast_grid_scan.kickoff()

    status.wait()

    verify(fast_grid_scan.run_cmd).set(1)
    assert status.exception() == None
