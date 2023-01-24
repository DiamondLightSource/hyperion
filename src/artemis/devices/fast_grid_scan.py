import threading
import time
from dataclasses import dataclass

from bluesky.plan_stubs import mv
from dataclasses_json import dataclass_json
from ophyd import (
    Component,
    Device,
    EpicsSignal,
    EpicsSignalRO,
    EpicsSignalWithRBV,
    Signal,
)
from ophyd.status import DeviceStatus, StatusBase

from artemis.devices.motors import XYZLimitBundle
from artemis.devices.status import await_value
from artemis.utils import Point3D


@dataclass
class GridAxis:
    start: float
    step_size: float
    full_steps: int

    def steps_to_motor_position(self, steps):
        return self.start + (steps * self.step_size)

    @property
    def end(self):
        return self.steps_to_motor_position(self.full_steps)

    def is_within(self, steps):
        return 0 <= steps <= self.full_steps


@dataclass_json
@dataclass
class GridScanParams:
    """
    Holder class for the parameters of a grid scan in a similar
    layout to EPICS.

    Motion program will do a grid in x-y then rotate omega +90 and perform
    a grid in x-z
    """

    x_steps: int = 1
    y_steps: int = 1
    z_steps: int = 0
    x_step_size: float = 0.1
    y_step_size: float = 0.1
    z_step_size: float = 0.1
    dwell_time: float = 0.1
    x_start: float = 0.1
    y1_start: float = 0.1
    y2_start: float = 0.1
    z1_start: float = 0.1
    z2_start: float = 0.1

    def __post_init__(self):
        self.x_axis = GridAxis(self.x_start, self.x_step_size, self.x_steps)
        self.y_axis = GridAxis(self.y1_start, self.y_step_size, self.y_steps)
        self.z_axis = GridAxis(self.z2_start, self.z_step_size, self.z_steps)
        self.axes = [self.x_axis, self.y_axis, self.z_axis]

    def is_valid(self, limits: XYZLimitBundle) -> bool:
        """
        Validates scan parameters

        :param limits: The motor limits against which to validate
                       the parameters
        :return: True if the scan is valid
        """
        x_in_limits = limits.x.is_within(self.x_axis.start) and limits.x.is_within(
            self.x_axis.end
        )
        y_in_limits = limits.y.is_within(self.y_axis.start) and limits.y.is_within(
            self.y_axis.end
        )

        first_grid_in_limits = (
            x_in_limits and y_in_limits and limits.z.is_within(self.z1_start)
        )

        z_in_limits = limits.z.is_within(self.z_axis.start) and limits.z.is_within(
            self.z_axis.end
        )

        second_grid_in_limits = (
            x_in_limits and z_in_limits and limits.y.is_within(self.y2_start)
        )

        return first_grid_in_limits and second_grid_in_limits

    @property
    def is_3d_grid_scan(self):
        return self.z_steps > 0

    def grid_position_to_motor_position(self, grid_position: Point3D) -> Point3D:
        """Converts a grid position, given as steps in the x, y, z grid,
        to a real motor position.

        :param grid_position: The x, y, z position in grid steps
        :return: The motor position this corresponds to.
        :raises: IndexError if the desired position is outside the grid."""
        for position, axis in zip(grid_position, self.axes):
            if not axis.is_within(position):
                raise IndexError(f"{grid_position} is outside the bounds of the grid")

        return Point3D(
            self.x_axis.steps_to_motor_position(grid_position.x),
            self.y_axis.steps_to_motor_position(grid_position.y),
            self.z_axis.steps_to_motor_position(grid_position.z),
        )


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
            self.clean_up()
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

    expected_images: Signal = Component(Signal)

    # Kickoff timeout in seconds
    KICKOFF_TIMEOUT: float = 5.0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        def set_expected_images(*_, **__):
            x, y, z = self.x_steps.get(), self.y_steps.get(), self.z_steps.get()
            first_grid = x * y
            second_grid = x * z
            self.expected_images.put(first_grid + second_grid)

        self.x_steps.subscribe(set_expected_images)
        self.y_steps.subscribe(set_expected_images)
        self.z_steps.subscribe(set_expected_images)

    def is_invalid(self) -> bool:
        if "GONP" in self.scan_invalid.pvname:
            return False
        return self.scan_invalid.get()

    def kickoff(self) -> StatusBase:
        # Check running already here?
        st = DeviceStatus(device=self, timeout=self.KICKOFF_TIMEOUT)

        def scan():
            try:
                self.log.debug("Running scan")
                self.run_cmd.put(1)
                self.log.debug("Waiting for scan to start")
                await_value(self.status, 1).wait()
                st.set_finished()
            except Exception as e:
                st.set_exception(e)

        threading.Thread(target=scan, daemon=True).start()
        return st

    def complete(self) -> DeviceStatus:
        return GridScanCompleteStatus(self)

    def collect(self):
        return {}

    def describe_collect(self):
        return {}


def set_fast_grid_scan_params(scan: FastGridScan, params: GridScanParams):
    yield from mv(
        scan.x_steps,
        params.x_steps,
        scan.y_steps,
        params.y_steps,
        scan.z_steps,
        params.z_steps,
        scan.x_step_size,
        params.x_step_size,
        scan.y_step_size,
        params.y_step_size,
        scan.z_step_size,
        params.z_step_size,
        scan.dwell_time,
        params.dwell_time,
        scan.x_start,
        params.x_start,
        scan.y1_start,
        params.y1_start,
        scan.y2_start,
        params.y2_start,
        scan.z1_start,
        params.z1_start,
        scan.z2_start,
        params.z2_start,
        scan.position_counter,
        0,
    )
