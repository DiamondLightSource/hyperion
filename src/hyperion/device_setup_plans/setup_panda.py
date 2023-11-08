from asyncio import subprocess

import bluesky.plan_stubs as bps
from ophyd_async.core import SignalRW, load_device
from ophyd_async.panda import PandA, seq_table_from_arrays, SeqTable

from hyperion.log import LOGGER
from hyperion.parameters.plan_specific.panda.panda_gridscan_internal_params import (
    PandaGridscanInternalParameters as GridscanInternalParameters,
)

ENCODER_TO_MM = 2000  # 20000 counts to a mm ? check this


def setup_panda_for_flyscan(
    panda: PandA, save_path: str, parameters: GridscanInternalParameters
):
    """This should load a 'base' panda-flyscan yaml file, then grid the grid parameters, then adjust the PandA
    sequencer table to match this new grid"""

    # This sets the PV's for a template panda fast grid scan, Load a template fast grid scan config,
    # uses /dls/science/users/qqh35939/panda_yaml_files/flyscan_base.yaml for now
    

    """
    
    -Setting a 'signal' means to PCAP internally and to Eiger via physical panda output
    -NOTE: When we wait for the position to be greater/lower, give some lee-way (~10 counts) as the encoder counts arent always exact
    SEQUENCER TABLE:
        1:Wait for physical trigger from motion script to mark start of scan / change of direction
        2:Wait for POSA (X2) to be greater than X_START, then
          send a signal out every 2000us (minimum eiger exposure time) + 4us (eiger dead time ((check that number)))
        3:Wait for POSA (X2) to be greater than X_START + (X_STEP_SIZE * NUM_X_STEPS), then cut out the signal
        4:Wait for physical trigger from motion script to mark change of direction
        5:Wait for POSA (X2) to be less than X_START + (X_STEP_SIZE * NUM_X_STEPS), then
          send a signal out every 2000us (minimum eiger exposure time) + 4us (eiger dead time ((check that number)))
        6:Wait for POSA (X2) to be less than X_START, then cut out signal
        7:Go back to step one. Scan should finish at step 6, and then not recieve any more physical triggers so the panda will stop sending outputs
        
        At this point, the panda blocks should be disarmed during the tidyup.
    """

    #First move smargon to start position
    yield from bps.abs_set((panda.inenc[1].setp, 0) #Home X2 encoder value
                           
    #Now construct the table...
    """    repeats: Optional[npt.NDArray[np.uint16]] = None,
    trigger: Optional[Sequence[SeqTrigger]] = None,
    position: Optional[npt.NDArray[np.int32]] = None,
    time1: Optional[npt.NDArray[np.uint32]] = None,
    outa1: Optional[npt.NDArray[np.bool_]] = None,
    outb1: Optional[npt.NDArray[np.bool_]] = None,
    outc1: Optional[npt.NDArray[np.bool_]] = None,
    outd1: Optional[npt.NDArray[np.bool_]] = None,
    oute1: Optional[npt.NDArray[np.bool_]] = None,
    outf1: Optional[npt.NDArray[np.bool_]] = None,
    time2: npt.NDArray[np.uint32],
    outa2: Optional[npt.NDArray[np.bool_]] = None,
    outb2: Optional[npt.NDArray[np.bool_]] = None,
    outc2: Optional[npt.NDArray[np.bool_]] = None,
    outd2: Optional[npt.NDArray[np.bool_]] = None,
    oute2: Optional[npt.NDArray[np.bool_]] = None,
    outf2: Optional[npt.NDArray[np.bool_]] = None,
) -> SeqTable:"""

    #Build table
                           
                           
    yield from bps.abs_set((panda.seq[1].table.))
                           
    """ The sequencer table should be adjusted as follows:
    - 
    - Use the gridscan parameters read from hyperion to update some of the panda PV's:
        - Move the Smargon to the grid-scan start position, then home each encoder
        - Find the conversion rate of encoder-values to mm. I think this is always the same
        - Adjust the sequencer table so that it waits for correct posotion (see above comment on sequencer table). Do this for all sequencer rows
    
        - The sequencer table needs to start and end at the correct positions. Make sure the conversion rate for counts to mm is correct 
          correctly zeroed
        - The smargon should be moved to the start position (slightly before the SEQ1 start position) before the sequencer is armed
        - Arm the relevant blocks before beginning the plan (this could be done in arm function)
    
    
    """


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
    # Arm PCAP
    ...


def disarm_panda():
    # Disarm PCAP. This will disarm the blocks which were armed in the setup
    ...
