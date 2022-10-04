from ophyd import Component, Device, Signal

from artemis.devices.synchrotron import Synchrotron


class SynchrotronMonitor(Device):

    synchrotron: Synchrotron = Component(Synchrotron)
    total_exposure_time_signal: Signal = Component(Signal, value=1)
    # Seconds of estimated beam instability following topup:
    time_beam_unstable_signal: Signal = Component(Signal)
    threshold_percentage_signal: Signal = Component(Signal)
    topup_gate_signal: Signal = Component(Signal, value=True)
    dummy_topup_gate_signal: Signal = Component(Signal, value=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.synchrotron.top_up.topup_end_countdown.subscribe(
            self.set_topup_gate_signal
        )

    def set_topup_gate_signal(self, *_, **__):
        self.topup_gate_signal.put(self.get_topup_gate())

    def get_topup_gate(self):
        total_exposure_time = self.total_exposure_time_signal.get()
        time_to_topup = self.synchrotron.top_up.topup_start_countdown.get()
        mode_precludes_gating = self._mode_precludes_gating(time_to_topup)
        sufficient_time_before_topup = self._sufficient_time_before_topup(
            time_to_topup, total_exposure_time
        )
        time_beam_unstable = self.time_beam_unstable_signal.get()
        threshold_percentage = self.threshold_percentage_signal.get()
        topup_degrades_exposure = self._topup_degrades_exposure(
            total_exposure_time, time_beam_unstable, threshold_percentage
        )
        delay_required = (
            not (mode_precludes_gating or sufficient_time_before_topup)
            and topup_degrades_exposure
        )
        """
        # for testing
        return [
            "not dummy",
            mode_precludes_gating,
            sufficient_time_before_topup,
            topup_degrades_exposure,
            delay_required,
        ]
        """
        return delay_required

    @staticmethod
    def _topup_degrades_exposure(
        total_exposure_time, time_beam_unstable, threshold_percentage
    ):
        # return True if topup duration eats a significant fraction of planned exposure time
        return 100.0 * time_beam_unstable / total_exposure_time > threshold_percentage

    def _mode_precludes_gating(self, time_to_topup):
        return (
            self._in_decay_mode(time_to_topup)
            or not self._gating_permitted_in_machine_mode()
        )

    def _gating_permitted_in_machine_mode(self):
        machine_mode = self.synchrotron.machine_status.synchrotron_mode.get()
        permitted_modes = ("User", "Special")
        return machine_mode in permitted_modes

    @staticmethod
    def _in_decay_mode(time_to_topup):
        # If this is -1 we're in decay mode so no need to gate as no topup
        return time_to_topup == -1

    @staticmethod
    def _sufficient_time_before_topup(time_to_topup, total_exposure_time):
        return time_to_topup > total_exposure_time
