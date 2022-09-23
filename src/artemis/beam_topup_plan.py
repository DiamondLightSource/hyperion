import time

from bluesky import RunEngine
from bluesky.plan_stubs import rd
from bluesky.suspenders import SuspendBoolHigh

from artemis.devices.synchrotron_monitor import SynchrotronMonitor
from artemis.topup_parameters import TopupParameters


def get_synchrotron_monitor_from_parameters(topup_monitor_args: TopupParameters):
    synchrotron_monitor = SynchrotronMonitor(
        name="synchrotron monitor", read_attrs=["topup_gate_signal"]
    )
    synchrotron_monitor.wait_for_connection()
    synchrotron_monitor.total_exposure_time_signal.put(
        topup_monitor_args.total_exposure_time
    )
    synchrotron_monitor.time_beam_unstable_signal.put(
        topup_monitor_args.instability_time
    )
    synchrotron_monitor.threshold_percentage_signal.put(
        topup_monitor_args.threshold_percentage
    )
    return synchrotron_monitor


def dummy_plan(synchrotron_monitor: SynchrotronMonitor):
    for i in range(600):
        time.sleep(1)
        value = yield from rd(synchrotron_monitor)
        print(f"Plan is running. Step {i}, topup_gate={value}")


if __name__ == "__main__":
    RE = RunEngine()
    topup_plan_args = TopupParameters()
    topup_plan_args.total_exposure_time = 100
    topup_plan_args.instability_time = 45
    topup_plan_args.threshold_percentage = 10
    synchrotron_monitor = get_synchrotron_monitor_from_parameters(topup_plan_args)
    sus = SuspendBoolHigh(synchrotron_monitor.topup_gate_signal)
    RE.install_suspender(sus)
    RE(dummy_plan(synchrotron_monitor))
