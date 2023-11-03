import bluesky.plan_stubs as bps
from ophyd_async.core import SignalRW, load_from_yaml
from ophyd_async.panda import PandA

from hyperion.log import LOGGER
from hyperion.utils.panda_utils import read_detector_output, read_fast_shutter_output


def setup_panda_for_flyscan(panda: PandA):
    """Setup the sequencer, pcap blocks and encoder I/O's for the flyscan.
    Parameters needed:
    Everything from FGS except swap dwell time for desired frame rate

    Right now this is specific to I03
    """

    ...


def disable_panda_blocks(panda: PandA):
    """Use this at the beginning of setting up a PandA to ensure any residual settings are ignored"""
    # devices = get_device_children(panda)

    # Loops through panda blocks with read access with an 'enable' signal, and set to 0

    ...


# This might not be needed. For the Zebra, this function configures the zebra to make its outputs correspond to
# The eiger and fast shutter, For the Panda, we should be able to do this all within the load.
# def setup_panda_shutter_to_manual(
#     panda: PandA, group="set_panda_shutter_to_manual", wait=False
# ):
#     # on I03, panda OUT1 goes to detector, OUT2 goes to shutter
#     yield from bps.abs_set(panda.ttlout[1].val, "ONE", group=group)
#     yield from bps.abs_set(zebra.output.out_pvs[TTL_SHUTTER], OR1, group=group)

#     if wait:
#         yield from bps.wait(group)


def arm_panda():
    """Arm PCAP"""
    ...


def disarm_panda():
    """Disarm PCAP"""
    ...
