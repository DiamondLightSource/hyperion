import threading
import time
from typing import List
from ophyd import Component, Device, EpicsSignal, EpicsSignalRO, EpicsSignalWithRBV
from ophyd.status import DeviceStatus, StatusBase, SubscriptionStatus


class GridScanCompleteStatus(DeviceStatus):
    """
    A Status for the grid scan completion
    A special status object that notifies watches (progress bars)
    based on comparing device.expected_images to device.position_counter.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_ts = time.time()

        # Notify watchers (things like progress bars) of new values
        self.device.position_counter.subscribe(self._notify_watchers)
        self.device.status.subscribe(self._running_changed)
        # some state needed only by self._notify_watchers
        self._name = self.device.name
        self._target_count = self.device.expected_images

    def _notify_watchers(self, value, *args, **kwargs):
        if not self._watchers:
            return
        time_elapsed = time.time() - self.start_ts
        try:
            fraction = value / self._target_count
        except ZeroDivisionError:
            fraction = 1
        except Exception:
            fraction = None
            time_remaining = None
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
    z_steps: EpicsSignalWithRBV = Component(EpicsSignalWithRBV, "Z_NUM_STEPS")

    x_step_size: EpicsSignalWithRBV = Component(EpicsSignalWithRBV, "X_STEP_SIZE")
    y_step_size: EpicsSignalWithRBV = Component(EpicsSignalWithRBV, "Y_STEP_SIZE")
    z_step_size: EpicsSignalWithRBV = Component(EpicsSignalWithRBV, "Z_STEP_SIZE")

    dwell_time: EpicsSignalWithRBV = Component(EpicsSignalWithRBV, "DWELL_TIME")

    x_start: EpicsSignalWithRBV = Component(EpicsSignalWithRBV, "X_START")
    y1_start: EpicsSignalWithRBV = Component(EpicsSignalWithRBV, "Y_START")
    y2_start: EpicsSignalWithRBV = Component(EpicsSignalWithRBV, "Y2_START")
    z1_start: EpicsSignalWithRBV = Component(EpicsSignalWithRBV, "Z_START")
    z2_start: EpicsSignalWithRBV = Component(EpicsSignalWithRBV, "Z2_START")

    position_counter: EpicsSignal = Component(
        EpicsSignal, "POS_COUNTER", write_pv="POS_COUNTER_WRITE"
    )
    x_counter: EpicsSignalRO = Component(EpicsSignalRO, "X_COUNTER")
    y_counter: EpicsSignalRO = Component(EpicsSignalRO, "Y_COUNTER")
    scan_invalid: EpicsSignalRO = Component(EpicsSignalRO, "SCAN_INVALID")

    run_cmd: EpicsSignal = Component(EpicsSignal, "RUN.PROC")
    stop_cmd: EpicsSignal = Component(EpicsSignal, "STOP.PROC")
    status: EpicsSignalRO = Component(EpicsSignalRO, "SCAN_STATUS")

    # Kickoff timeout in seconds
    KICKOFF_TIMEOUT: float = 5.0

    def set_program_data(self, nx, ny, width, height, exptime, startx, starty, startz):
        self.x_steps.put(nx)
        self.y_steps.put(ny)
        self.x_step_size.put(float(width))
        self.y_step_size.put(float(height))
        self.dwell_time.put(float(exptime))
        self.x_start.put(float(startx))
        self.y1_start.put(float(starty))
        self.z1_start.put(float(startz))
        self.expected_images = nx * ny

    def is_invalid(self):
        if "GONP" in self.scan_invalid.pvname:
            return False
        return self.scan_invalid.get()

    def kickoff(self) -> StatusBase:
        # Check running already here?
        st = DeviceStatus(device=self, timeout=self.KICKOFF_TIMEOUT)

        def check_valid():
            self.log.info("Waiting on position counter reset and valid settings")
            while self.is_invalid() and not self.position_counter.get() == 0:
                time.sleep(0.1)
            self.log.debug("Running scan")
            running = SubscriptionStatus(self.status, lambda value: value == 1)
            run_requested = self.run_cmd.set(1)
            (run_requested and running).wait()
            st.set_finished()

        threading.Thread(target=check_valid, daemon=True).start()
        return st

    def stage(self) -> List[object]:
        self.position_counter.put(0)
        return super().stage()

    def complete(self) -> StatusBase:
        return GridScanCompleteStatus(self)
