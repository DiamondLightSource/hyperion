import time

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
from ophyd.sim import SynSignal, det1, det2

detectors = [det1, det2]
signal0 = SynSignal(name="undulator_gap")
signal1 = SynSignal(name="synchrotron_machine_status_synchrotron_mode")
signal2 = SynSignal(name="slit_gaps_xgap")
signal3 = SynSignal(name="slit_gaps_ygap")


def fake_update_ispyb_params():
    yield from bps.create(name="fake_ispyb_motor_positions")
    yield from bps.read(signal0)
    yield from bps.read(signal1)
    yield from bps.read(signal2)
    yield from bps.read(signal3)
    yield from bps.save()


@bpp.run_decorator()
def run_fake_scan(
    md={
        # The name of this plan
        "plan_name": "fake_scan",
    }
):

    yield from fake_update_ispyb_params()

    # Delays are basically here to make graylog logs appear in ~order
    for det in detectors:
        yield from bps.stage(det)
        time.sleep(0.1)  # fake stagiing should take some time

    yield from bps.trigger_and_read(detectors)
    time.sleep(0.1)  # fake plan should take some time

    for det in detectors:
        yield from bps.unstage(det)
        time.sleep(0.05)  # fake unstaging should take some time


def get_fake_scan():
    return run_fake_scan()
