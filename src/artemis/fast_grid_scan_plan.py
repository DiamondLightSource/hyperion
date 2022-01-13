import bluesky.preprocessors as bpp
import bluesky.plan_stubs as bps
from src.artemis.devices.zebra import Zebra
from ophyd.device import Device
from ophyd.sim import make_fake_device

# Clear odin errors and check initialised
# If in error clean up
# Setup beamline
# Store in ISPyB
# Start nxgen
# Start analysis run collection
# Run gridscan


@bpp.run_decorator()
def run_gridscan(fgs, zebra: Zebra, eiger):
    # Check topup gate
    # Configure FGS

    @bpp.stage_decorator([zebra, eiger, fgs])
    def do_fgs():
        yield from bps.kickoff(fgs)
        yield from bps.complete(fgs, wait=True)

    return (yield from do_fgs())
