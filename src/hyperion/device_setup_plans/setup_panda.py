import bluesky.plan_stubs as bps
from ophyd_async.panda import PandA

from hyperion.log import LOGGER


def setup_panda_for_flyscan():
    """Setup the sequencer, pcap blocks and encoder I/O's for the flyscan.
    Parameters needed:
    Everything from FGS except swap dwell time for desired frame rate

    """
    ...


def disable_panda_blocks(panda: PandA):
    """Use this at the beginning of setting up a PandA to ensure any residual settings are ignored"""
    # devices = get_device_children(panda)

    # Loops through panda blocks with read access with an 'enable' signal, and set to 0

    ...


def arm_panda():
    """Arm PCAP"""
    ...


def disarm_panda():
    """Disarm PCAP"""
    ...
