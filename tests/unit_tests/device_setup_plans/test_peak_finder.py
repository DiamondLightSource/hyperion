from bluesky import Msg
from dodal.devices.DCM import DCM
from dodal.devices.qbpm1 import QBPM1

from hyperion.device_setup_plans.peak_finder import (
    SimpleMaximumPeakEstimator,
    SingleScanPassPeakFinder,
)
from hyperion.log import LOGGER

from ..conftest import RunEngineSimulator


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


def test_single_scan_pass_peak_finder(dcm: DCM, qbpm1: QBPM1):
    sim = RunEngineSimulator()
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
    sim.simulate_plan(
        peak_finder.find_peak_plan(dcm.pitch, qbpm1.intensityC, 5, 0.9, 0.1)
    )
    # assert (messages := assert_message_and_return_remaining(messages, lambda msg: )


def dump(generator):
    g = generator
    if callable(g):
        g = g()

    sendval = None
    while True:
        try:
            yielded = g.send(sendval)
            LOGGER.info(f"yielded {yielded}")
            sendval = yield yielded
        except StopIteration:
            break
