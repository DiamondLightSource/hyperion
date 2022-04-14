import pytest
from bluesky.run_engine import RunEngine
from mockito import mock, unstub, verify, when
from mockito.matchers import ANY, ARGS, KWARGS
from ophyd.sim import make_fake_device
from src.artemis.devices.fast_grid_scan import (
    FastGridScan,
    GridScanParams,
    scan_in_limits,
    set_fast_grid_scan_params,
    time,
)
from src.artemis.devices.motors import GridScanMotorBundle


@pytest.fixture
def fast_grid_scan():
    FakeFastGridScan = make_fake_device(FastGridScan)
    fast_grid_scan: FastGridScan = FakeFastGridScan(name="test")
    fast_grid_scan.scan_invalid.pvname = ""

    # A bit of a hack to assume that if we are waiting on something then we will timeout
    when(time).sleep(ANY).thenRaise(TimeoutError())
    yield fast_grid_scan
    # Need to unstub as sleep raising a TimeoutError can cause a segfault on the destruction of FastGridScan
    unstub()


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
    when(fast_grid_scan.run_cmd).put(ANY).thenReturn(mock_run_set_status)
    fast_grid_scan.status.subscribe = lambda func, **_: func(1)

    status = fast_grid_scan.kickoff()

    status.wait()

    verify(fast_grid_scan.run_cmd).put(1)


def run_test_on_complete_watcher(
    fast_grid_scan: FastGridScan, num_pos_1d, put_value, expected_frac
):
    RE = RunEngine()
    RE(
        set_fast_grid_scan_params(
            fast_grid_scan, GridScanParams(num_pos_1d, num_pos_1d)
        )
    )

    complete_status = fast_grid_scan.complete()
    watcher = mock()
    complete_status.watch(watcher)

    fast_grid_scan.position_counter.sim_put(put_value)
    verify(watcher).__call__(
        *ARGS,
        current=put_value,
        target=num_pos_1d**2,
        fraction=expected_frac,
        **KWARGS,
    )
    return complete_status


def test_when_new_image_then_complete_watcher_notified(fast_grid_scan: FastGridScan):
    run_test_on_complete_watcher(fast_grid_scan, 2, 1, 3 / 4)


def test_given_0_expected_images_then_complete_watcher_correct(
    fast_grid_scan: FastGridScan,
):
    run_test_on_complete_watcher(fast_grid_scan, 0, 1, 0)


def test_given_invalid_image_number_then_complete_watcher_correct(
    fast_grid_scan: FastGridScan,
):
    complete_status = run_test_on_complete_watcher(fast_grid_scan, 1, "BAD", None)
    assert complete_status.exception()


def test_running_finished_with_all_images_done_then_complete_status_finishes_not_in_error(
    fast_grid_scan: FastGridScan,
):
    num_pos_1d = 2
    RE = RunEngine()
    RE(
        set_fast_grid_scan_params(
            fast_grid_scan, GridScanParams(num_pos_1d, num_pos_1d)
        )
    )

    fast_grid_scan.status.sim_put(1)

    complete_status = fast_grid_scan.complete()
    assert not complete_status.done
    fast_grid_scan.position_counter.sim_put(num_pos_1d**2)
    fast_grid_scan.status.sim_put(0)

    complete_status.wait()

    assert complete_status.done
    assert complete_status.exception() is None


def create_motor_bundle_with_x_limits(low_limit, high_limit) -> GridScanMotorBundle:
    FakeGridScanMotorBundle = make_fake_device(GridScanMotorBundle)
    grid_scan_motor_bundle: GridScanMotorBundle = FakeGridScanMotorBundle(name="test")
    grid_scan_motor_bundle.wait_for_connection()
    grid_scan_motor_bundle.x.low_limit_travel.sim_put(low_limit)
    grid_scan_motor_bundle.x.high_limit_travel.sim_put(high_limit)
    return grid_scan_motor_bundle


@pytest.mark.parametrize(
    "position, expected_in_limit",
    [
        (-1, False),
        (20, False),
        (5, True),
    ],
)
def test_within_limits_check(position, expected_in_limit):
    limits = create_motor_bundle_with_x_limits(0.0, 10).get_limits()
    assert limits.x.is_within(position) == expected_in_limit


@pytest.mark.parametrize(
    "start, steps, size, expected_in_limits",
    [
        (1, 5, 1, True),
        (-1, 5, 1, False),
        (-1, 10, 2, False),
        (0, 10, 0.1, True),
        (5, 10, 0.5, True),
        (5, 20, 0.6, False),
    ],
)
def test_scan_within_limits(start, steps, size, expected_in_limits):
    motor_bundle = create_motor_bundle_with_x_limits(0.0, 10.0)
    assert (
        scan_in_limits(motor_bundle.get_limits().x, start, steps, size)
        == expected_in_limits
    )
