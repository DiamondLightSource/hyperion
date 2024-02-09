from bluesky.run_engine import RunEngine
from dodal.beamlines.i03 import zebra

from hyperion.device_setup_plans.setup_zebra import setup_zebra_for_panda_flyscan

if __name__ == "__main__":
    RE = RunEngine()
    zebra_device = zebra()
    RE(setup_zebra_for_panda_flyscan(zebra, wait=True))
