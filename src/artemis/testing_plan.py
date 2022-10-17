import time

import bluesky.plan_stubs as bps
from ophyd.sim import det1, det2

detectors = [det1, det2]


def run_fake_scan():
    for det in detectors:
        yield from bps.stage(det)

    yield from bps.open_run()
    yield from bps.trigger_and_read(detectors)
    time.sleep(0.1)  # fake plan should take some time

    yield from bps.close_run()

    for det in detectors:
        yield from bps.unstage(det)


def get_fake_scan():
    return run_fake_scan()
