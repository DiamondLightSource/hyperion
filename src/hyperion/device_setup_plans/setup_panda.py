from asyncio import subprocess

import bluesky.plan_stubs as bps
import numpy as np
from dodal.devices.panda_fast_grid_scan import PandaGridScanParams
from ophyd_async.core import SignalRW, load_device
from ophyd_async.panda import PandA, SeqTable, SeqTrigger, seq_table_from_arrays

from hyperion.log import LOGGER
from hyperion.parameters.plan_specific.panda.panda_gridscan_internal_params import (
    PandaGridscanInternalParameters as GridscanInternalParameters,
)

ENCODER_TO_MM = 2000  # 20000 counts to a mm ? check this
GENERAL_TIMEOUT = 60


def setup_panda_for_flyscan(
    panda: PandA, save_path: str, parameters: PandaGridScanParams, initial_x: float
):
    """This should load a 'base' panda-flyscan yaml file, then grid the grid parameters, then adjust the PandA
    sequencer table to match this new grid"""

    # This sets the PV's for a template panda fast grid scan, Load a template fast grid scan config,
    # uses /dls/science/users/qqh35939/panda_yaml_files/flyscan_base.yaml for now
    yield from load_device(panda, save_path)

    # Home X2 encoder value : Do we want to measure X relative to the start of the grid scan or as an absolute position?
    yield from bps.abs_set((panda.inenc[1].setp, initial_x * ENCODER_TO_MM))

    """   
    -Setting a 'signal' means trigger PCAP internally and send signal to Eiger via physical panda output
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

    # Construct sequencer 1 table
    trigger = [
        SeqTrigger.BITA_1,
        SeqTrigger.POSA_GT,
        SeqTrigger.POSA_GT,
        SeqTrigger.BITA_1,
        SeqTrigger.POSA_LT,
        SeqTrigger.POSA_LT,
    ]
    position = np.array(
        [
            0,
            (parameters.x_start * ENCODER_TO_MM),
            (parameters.x_start * ENCODER_TO_MM)
            + (parameters.x_steps * parameters.x_step_size) * ENCODER_TO_MM
            - 15,
            0,
            (parameters.x_start * ENCODER_TO_MM)
            + (parameters.x_steps * parameters.x_step_size * ENCODER_TO_MM),
            (parameters.x_start * ENCODER_TO_MM) + 15,
        ]
    )
    outa1 = np.array([False, True, False, False, True, False])
    time2 = np.array([1, 1, 1, 1, 1, 1])
    outa2 = np.array([1, 1, 1, 1, 1, 1])

    seq_table: SeqTable = seq_table_from_arrays(
        trigger=trigger, position=position, outa1=outa1, time2=time2, outa2=outa2
    )

    yield from bps.abs_set(panda.seq[1].table, seq_table)

    # yield from bps.abs_set((panda.seq[1].table.))

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


def arm_panda_for_gridscan(panda: PandA, group="arm_panda_gridscan", wait=False):
    yield from bps.abs_set(panda.seq[1].enable, True, group=group)
    yield from bps.abs_set(panda.clock[1].enable, True, group=group)
    yield from bps.abs_set(panda.pulse[1].enable, True, group=group)
    yield from bps.wait(group="arm_panda_gridscan", timeout=GENERAL_TIMEOUT)
    if wait:
        yield from bps.wait(group=group, timeout=GENERAL_TIMEOUT)


def disarm_panda_for_gridscan(panda, group="disarm_panda_gridscan", wait=False):
    yield from bps.abs_set(panda.seq[1].enable, False, group=group)
    yield from bps.abs_set(panda.clock[1].enable, False, group=group)
    yield from bps.abs_set(panda.pulse[1].enable, False, group=group)
    yield from bps.wait(group="disarm_panda_gridscan", timeout=GENERAL_TIMEOUT)
    if wait:
        yield from bps.wait(group=group, timeout=GENERAL_TIMEOUT)
