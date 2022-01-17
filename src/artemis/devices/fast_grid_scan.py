import threading
import time
from typing import List
from ophyd import (
    Component,
    Device,
    EpicsSignal,
    EpicsSignalRO,
    EpicsSignalWithRBV,
    Signal,
)
from ophyd.status import DeviceStatus, StatusBase, SubscriptionStatus

from dataclasses import dataclass
from typing import Any

from src.artemis.devices.motors import (
    GridScanLimit,
    GridScanLimitBundle,
)

from bluesky.plan_stubs import mv


@dataclass
class GridScanParams:
    """
    Holder class for the parameters of a grid scan.
    """

    x_steps: int = 1
    y_steps: int = 1
    x_step_size: float = 0.1
    y_step_size: float = 0.1
    dwell_time: float = 0.1
    x_start: float = 0.1
    y1_start: float = 0.1
    z1_start: float = 0.1

    def is_valid(self, limits: GridScanLimitBundle) -> bool:
        """
        Validates scan parameters

        :param limits: The motor limits against which to validate
                       the parameters
        :return: True if the scan is valid
        """

        return (
            # All scan axes are within limits
            scan_in_limits(limits.x, self.x_start, self.x_steps, self.x_step_size)
            and scan_in_limits(limits.y, self.y1_start, self.y_steps, self.y_step_size)
            # Z never exceeds limits
            and limits.z.is_within(self.z1_start)
        )


def scan_in_limits(
    limit: GridScanLimit, start: float, steps: float, step_size: float
) -> bool:
    end = start + (steps * step_size)
    return limit.is_within(start) and limit.is_within(end)


class GridScanCompleteStatus(DeviceStatus):
    """
    A Status for the grid scan completion
    A special status object that notifies watchers (progress bars)
    based on comparing device.expected_images to device.position_counter.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_ts = time.time()

        self.device.position_counter.subscribe(self._notify_watchers)
        self.device.status.subscribe(self._running_changed)

        self._name = self.device.name
        self._target_count = self.device.expected_images.get()

    def _notify_watchers(self, value, *args, **kwargs):
        if not self._watchers:
            return
        time_elapsed = time.time() - self.start_ts
        try:
            fraction = 1 - value / self._target_count
        except ZeroDivisionError:
            fraction = 0
            time_remaining = 0
        except Exception as e:
            fraction = None
            time_remaining = None
            self.set_exception(e)
        else:
            time_remaining = time_elapsed / fraction
        for watcher in self._watchers:
            watcher(
                name=self._name,
                current=value,
                initial=0,
                target=self._target_count,
                unit="images",
                precision=0,
                fraction=fraction,
                time_elapsed=time_elapsed,
                time_remaining=time_remaining,
            )

    def _running_changed(self, value=None, old_value=None, **kwargs):
        if (old_value == 1) and (value == 0):
            # Stopped running
            number_of_images = self.device.position_counter.get()
            if number_of_images != self._target_count:
                self.set_exception(
                    Exception(
                        f"Grid scan finished without collecting expected number of images. Expected {self._target_count} got {number_of_images}."
                    )
                )
            else:
                self.set_finished()
            self.clean_up()

    def clean_up(self):
        self.device.position_counter.clear_sub(self._notify_watchers)
        self.device.status.clear_sub(self._running_changed)


class FastGridScan(Device):

    x_steps: EpicsSignalWithRBV = Component(EpicsSignalWithRBV, "X_NUM_STEPS")
    y_steps: EpicsSignalWithRBV = Component(EpicsSignalWithRBV, "Y_NUM_STEPS")

    x_step_size: EpicsSignalWithRBV = Component(EpicsSignalWithRBV, "X_STEP_SIZE")
    y_step_size: EpicsSignalWithRBV = Component(EpicsSignalWithRBV, "Y_STEP_SIZE")

    dwell_time: EpicsSignalWithRBV = Component(EpicsSignalWithRBV, "DWELL_TIME")

    x_start: EpicsSignalWithRBV = Component(EpicsSignalWithRBV, "X_START")
    y1_start: EpicsSignalWithRBV = Component(EpicsSignalWithRBV, "Y_START")
    z1_start: EpicsSignalWithRBV = Component(EpicsSignalWithRBV, "Z_START")

    position_counter: EpicsSignal = Component(
        EpicsSignal, "POS_COUNTER", write_pv="POS_COUNTER_WRITE"
    )
    x_counter: EpicsSignalRO = Component(EpicsSignalRO, "X_COUNTER")
    y_counter: EpicsSignalRO = Component(EpicsSignalRO, "Y_COUNTER")
    scan_invalid: EpicsSignalRO = Component(EpicsSignalRO, "SCAN_INVALID")

    run_cmd: EpicsSignal = Component(EpicsSignal, "RUN.PROC")
    stop_cmd: EpicsSignal = Component(EpicsSignal, "STOP.PROC")
    status: EpicsSignalRO = Component(EpicsSignalRO, "SCAN_STATUS")

    expected_images: Signal = Component(Signal)

    # Kickoff timeout in seconds
    KICKOFF_TIMEOUT: float = 5.0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        def set_expected_images(*_, **__):
            self.expected_images.put(self.x_steps.get() * self.y_steps.get())

        self.x_steps.subscribe(set_expected_images)
        self.y_steps.subscribe(set_expected_images)

    def is_invalid(self) -> bool:
        if "GONP" in self.scan_invalid.pvname:
            return False
        return self.scan_invalid.get()

    def kickoff(self) -> StatusBase:
        # Check running already here?
        st = DeviceStatus(device=self, timeout=self.KICKOFF_TIMEOUT)

        def check_valid_and_scan():
            try:
                self.log.debug("Waiting on position counter reset and valid settings")
                while self.is_invalid() or not self.position_counter.get() == 0:
                    time.sleep(0.1)
                self.log.debug("Running scan")
                running = SubscriptionStatus(
                    self.status, lambda old_value, value, **kwargs: value == 1
                )
                self.run_cmd.put(1)
                self.log.debug("Waiting for scan to start")
                running.wait()
                st.set_finished()
            except Exception as e:
                st.set_exception(e)

        threading.Thread(target=check_valid_and_scan, daemon=True).start()
        return st

    def stage(self) -> List[object]:
        status = self.position_counter.set(0)
        status.wait()
        return super().stage()

    def complete(self) -> DeviceStatus:
        return GridScanCompleteStatus(self)


def set_fast_grid_scan_params(scan: FastGridScan, params: GridScanParams):
    yield from mv(
        scan.x_steps,
        params.x_steps,
        scan.y_steps,
        params.y_steps,
        scan.x_step_size,
        params.x_step_size,
        scan.y_step_size,
        params.y_step_size,
        scan.dwell_time,
        params.dwell_time,
        scan.x_start,
        params.x_start,
        scan.y1_start,
        params.y1_start,
        scan.z1_start,
        params.z1_start,
    )
