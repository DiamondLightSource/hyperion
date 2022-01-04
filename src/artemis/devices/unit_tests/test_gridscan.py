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


def run_test_on_complete_watcher(fast_grid_scan, num_pos_1d, put_value, expected_frac):
    fast_grid_scan.set_program_data(
        num_pos_1d, num_pos_1d, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
    )

    complete_status = fast_grid_scan.complete()
    watcher = mock()
    complete_status.watch(watcher)

    fast_grid_scan.position_counter.sim_put(put_value)
    verify(watcher).__call__(
        *ARGS,
        current=put_value,
        target=num_pos_1d ** 2,
        fraction=expected_frac,
        **KWARGS
    )


def test_when_new_image_then_complete_watcher_notified(fast_grid_scan: FastGridScan):
    run_test_on_complete_watcher(fast_grid_scan, 2, 1, 1 / 4)


def test_given_0_expected_images_then_complete_watcher_correct(
    fast_grid_scan: FastGridScan,
):
    run_test_on_complete_watcher(fast_grid_scan, 0, 1, 1)


def test_given_invalid_image_number_then_complete_watcher_correct(
    fast_grid_scan: FastGridScan,
):
    run_test_on_complete_watcher(fast_grid_scan, 1, "BAD", None)


def test_running_finished_with_not_all_images_done_then_complete_status_in_error(
    fast_grid_scan: FastGridScan,
):
    num_pos_1d = 2
    fast_grid_scan.set_program_data(
        num_pos_1d, num_pos_1d, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
    )

    fast_grid_scan.status.sim_put(1)

    complete_status = fast_grid_scan.complete()
    assert not complete_status.done
    fast_grid_scan.status.sim_put(0)

    with pytest.raises(Exception):
        complete_status.wait()

    assert complete_status.done
    assert complete_status.exception() != None


def test_running_finished_with_all_images_done_then_complete_status_finishes_not_in_error(
    fast_grid_scan: FastGridScan,
):
    num_pos_1d = 2
    fast_grid_scan.set_program_data(
        num_pos_1d, num_pos_1d, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
    )

    fast_grid_scan.status.sim_put(1)

    complete_status = fast_grid_scan.complete()
    assert not complete_status.done
    fast_grid_scan.position_counter.sim_put(num_pos_1d ** 2)
    fast_grid_scan.status.sim_put(0)

    complete_status.wait()

    assert complete_status.done
    assert complete_status.exception() == None
