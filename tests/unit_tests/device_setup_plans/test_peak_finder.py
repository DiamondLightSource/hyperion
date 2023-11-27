from math import isclose

from bluesky import Msg
from dodal.devices.DCM import DCM
from dodal.devices.qbpm1 import QBPM1

from hyperion.device_setup_plans.peak_finder import (
    SimpleMaximumPeakEstimator,
    SingleScanPassPeakFinder,
)


def test_simple_max_peak_estimator():
    test_data = [(1, 1), (1.5, 1.5), (2, 3.1), (2.5, 4.3), (3, 2.0), (4.5, 2.5)]
    estimator = SimpleMaximumPeakEstimator()
    assert estimator.estimate_peak(test_data) == 2.5


class FakeDCMPitchHandler:
    _pitch = 0
    _intensities = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
    _i = -1

    def set_pitch(self, msg: Msg):
        self._pitch = msg.args[0]

    def read_pitch(self, msg):
        return {"values": {"value": self._pitch}}

    def doc(self, msg):
        self._i += 1
        return {
            "data": {
                "dcm_pitch_user_setpoint": self._pitch,
                "qbpm1_intensityC": self._intensities[self._i],
            }
        }


def test_single_scan_pass_peak_finder(dcm: DCM, qbpm1: QBPM1, sim):
    peak_finder = SingleScanPassPeakFinder(SimpleMaximumPeakEstimator())
    pitch_handler = FakeDCMPitchHandler()
    sim.add_handler_for_callback_subscribes()
    sim.add_handler(
        "read", "dcm_pitch_user_setpoint", lambda msg: pitch_handler.read_pitch(msg)
    )
    sim.add_handler("set", "dcm_pitch", lambda msg: pitch_handler.set_pitch(msg))
    sim.add_handler(
        "save", None, lambda msg: sim.fire_callback("event", pitch_handler.doc(msg))
    )

    messages = sim.simulate_plan(
        peak_finder.find_peak_plan(dcm.pitch, qbpm1.intensityC, 5, 0.9, 0.1)
    )

    # Inside the run the peak finder performs the scan
    messages = sim.assert_message_and_return_remaining(
        messages, lambda msg: msg.command == "open_run"
    )

    def assert_one_step(messages, expected_x):
        try:
            messages = sim.assert_message_and_return_remaining(
                messages[1:],
                lambda msg: msg.command == "set"
                and msg.obj.name == "dcm_pitch"
                and isclose(msg.args[0], expected_x),
            )
            messages = sim.assert_message_and_return_remaining(
                messages[1:], lambda msg: msg.command == "wait"
            )
            messages = sim.assert_message_and_return_remaining(
                messages[1:], lambda msg: msg.command == "create"
            )
            messages = sim.assert_message_and_return_remaining(
                messages[1:],
                lambda msg: msg.command == "read"
                and msg.obj.name == "dcm_pitch_user_setpoint",
            )
            messages = sim.assert_message_and_return_remaining(
                messages[1:],
                lambda msg: msg.command == "read"
                and msg.obj.name == "qbpm1_intensityC",
            )
            return sim.assert_message_and_return_remaining(
                messages[1:], lambda msg: msg.command == "save"
            )
        except Exception as e:
            raise AssertionError(f"expected_x = {expected_x}") from e

    for i in range(0, 19):
        messages = assert_one_step(messages, 4.1 + 0.1 * i)

    # assert the final move to peak
    messages = sim.assert_message_and_return_remaining(
        messages[1:], lambda msg: msg.command == "close_run"
    )
    messages = sim.assert_message_and_return_remaining(
        messages[1:],
        lambda msg: msg.command == "set"
        and msg.obj.name == "dcm_pitch"
        and msg.args == (5,),
    )
    sim.assert_message_and_return_remaining(
        messages[1:], lambda msg: msg.command == "wait"
    )
