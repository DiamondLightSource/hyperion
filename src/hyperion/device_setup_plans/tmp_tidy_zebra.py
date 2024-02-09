from bluesky.run_engine import RunEngine
from dodal.beamlines.i03 import zebra

from hyperion.device_setup_plans.setup_zebra import set_zebra_shutter_to_manual

if __name__ == "__main__":
    RE = RunEngine()
    zebra_device = zebra()
    RE(set_zebra_shutter_to_manual(zebra_device, wait=True))
