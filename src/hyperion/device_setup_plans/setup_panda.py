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

MM_TO_ENCODER_COUNTS = 200000
GENERAL_TIMEOUT = 60
DEADTIME_S = 1e-6 #according to https://www.dectris.com/en/detectors/x-ray-detectors/eiger2/eiger2-for-synchrotrons/eiger2-x/

TIME_BETWEEN_X_STEPS_S = 4.1e-3 #TODO: Link this to the PV and add as a parameter


def setup_panda_for_flyscan(
    panda: PandA,
    config_yaml_path: str,
    parameters: PandaGridScanParams,
    initial_x: float,
    exposure_time_s: float,
):
    """This should load a 'base' panda-flyscan yaml file, then grid the grid parameters, then adjust the PandA
    sequencer table to match this new grid"""

    # This sets the PV's for a template panda fast grid scan, Load a template fast grid scan config,
    # uses /dls/science/users/qqh35939/panda_yaml_files/flyscan_base.yaml for now
    yield from load_device(panda, config_yaml_path)

    # Home X2 encoder value : Do we want to measure X relative to the start of the grid scan or as an absolute position?
    yield from bps.abs_set(
        panda.inenc[1].setp, initial_x * MM_TO_ENCODER_COUNTS, wait=True
    )
    LOGGER.info(f"Initialising panda to {initial_x} mm, {initial_x * MM_TO_ENCODER_COUNTS} counts")

    # Make sure the eiger trigger should be sent every time = (exposure time + deadtime). Assume deadtime is 10 microseconds (check)
    yield from bps.abs_set(panda.clock[1].period, DEADTIME_S + exposure_time_s)

    # The trigger width should last the same length as the exposure time
    yield from bps.abs_set(panda.pulse[1].width, 1e-8) #TODO at some point, thinnk about what constant this shoudl be

    """   
    -Setting a 'signal' means trigger PCAP internally and send signal to Eiger via physical panda output
    -NOTE: When we wait for the position to be greater/lower, give some lee-way (X_STEP_SIZE/2 * MM_TO_ENCODER counts) as the encoder counts arent always exact
    SEQUENCER TABLE:
        1:Wait for physical trigger from motion script to mark start of scan / change of direction
        2:Wait for POSA (X2) to be greater than X_START, then
          send a signal out every 2000us (minimum eiger exposure time) + 4us (eiger dead time ((check that number)))
        3:Wait for POSA (X2) to be greater than X_START + X_STEP_SIZE, then cut out the signal
        4:Wait for physical trigger from motion script to mark change of direction
        5:Wait for POSA (X2) to be less than X_START + X_STEP_SIZE, then
          send a signal out every 2000us (minimum eiger exposure time) + 4us (eiger dead time ((check that number)))
        6:Wait for POSA (X2) to be less than X_START, then cut out signal
        7:Go back to step one. Scan should finish at step 6, and then not recieve any more physical triggers so the panda will stop sending outputs 
        At this point, the panda blocks should be disarmed during the tidyup.
        
        EDIT:
        +ve and negative direction needs to have slightly different position values so the average position of the exposure time is the same. While in the negative direction, we should start the triggers at an earlier position:
        take away velocity (mm/s) * exposure_time (s) * MM_TO_ENCODER_COUNTS from the corresponding table values
    """
    
    #Velocity set by this calculation in panda grid scan motion script
    panda_velocity_mm_per_s = parameters.x_step_size/TIME_BETWEEN_X_STEPS_S
    

    # Construct sequencer 1 table.
    # trigger = [
    #     SeqTrigger.BITA_1,
    #     SeqTrigger.POSA_GT,
    #     SeqTrigger.POSA_GT,
    #     SeqTrigger.BITA_1,
    #     SeqTrigger.POSA_LT,
    #     SeqTrigger.POSA_LT,
    # ]
    # position = np.array(
    #     [
    #         0,
    #         (parameters.x_start * MM_TO_ENCODER_COUNTS),
    #         (parameters.x_start * MM_TO_ENCODER_COUNTS)
    #         + (parameters.x_step_size) * MM_TO_ENCODER_COUNTS
    #         - 15,
    #         0,
    #         (parameters.x_start * MM_TO_ENCODER_COUNTS)
    #         + (parameters.x_step_size * MM_TO_ENCODER_COUNTS),
    #         (parameters.x_start * MM_TO_ENCODER_COUNTS) + 15,
    #     ]
    # )
    # outa1 = np.array([0, 1, 0, 0, 1, 0])
    # time2 = np.array([1, 1, 1, 1, 1, 1])
    # outa2 = np.array([0, 1, 0, 0, 1, 0])

    # seq_table: SeqTable = seq_table_from_arrays(
    #     trigger=trigger, position=position, outa1=outa1, time2=time2, outa2=outa2
    # )

    # The above function didn't work when testing on I03, so set the table more manually

    table = SeqTable(
        repeats=np.array([1, 1, 1, 1, 1, 1]).astype(np.uint16),
        trigger=(
            SeqTrigger.BITA_1,
            SeqTrigger.POSA_GT,
            SeqTrigger.POSA_GT,
            SeqTrigger.BITA_1,
            SeqTrigger.POSA_LT,
            SeqTrigger.POSA_LT,
        ),
        position=np.array(
            [
                0,
                (parameters.x_start * MM_TO_ENCODER_COUNTS),
                (parameters.x_start * MM_TO_ENCODER_COUNTS)
                + (
                    parameters.x_step_size
                    * (
                        parameters.x_steps - 1
                    )  # x_start is the first trigger point, so we need to travel to x_steps-1 for the final triger point
                    * MM_TO_ENCODER_COUNTS + (MM_TO_ENCODER_COUNTS*(parameters.x_step_size/2))
                ),
                0,
                (parameters.x_start * MM_TO_ENCODER_COUNTS)
                + (
                    parameters.x_step_size
                    * (parameters.x_steps - 1)
                    * MM_TO_ENCODER_COUNTS + (panda_velocity_mm_per_s*exposure_time_s*MM_TO_ENCODER_COUNTS)
                ),
                (parameters.x_start * MM_TO_ENCODER_COUNTS - (MM_TO_ENCODER_COUNTS*(parameters.x_step_size/2)) + (panda_velocity_mm_per_s*exposure_time_s*MM_TO_ENCODER_COUNTS)),
            ],
            dtype=np.int32,
        ),
        time1=np.array([0, 0, 0, 0, 0, 0]).astype(np.uint32),
        outa1=np.array([0, 1, 0, 0, 1, 0]).astype(np.bool_),
        outb1=np.array([0, 0, 0, 0, 0, 0]).astype(np.bool_),
        outc1=np.array([0, 0, 0, 0, 0, 0]).astype(np.bool_),
        outd1=np.array([0, 0, 0, 0, 0, 0]).astype(np.bool_),
        oute1=np.array([0, 0, 0, 0, 0, 0]).astype(np.bool_),
        outf1=np.array([0, 0, 0, 0, 0, 0]).astype(np.bool_),
        time2=np.array([1, 1, 1, 1, 1, 1]).astype(np.uint32),
        outa2=np.array([0, 1, 0, 0, 1, 0]).astype(np.bool_),
        outb2=np.array([0, 0, 0, 0, 0, 0]).astype(np.bool_),
        outc2=np.array([0, 0, 0, 0, 0, 0]).astype(np.bool_),
        outd2=np.array([0, 0, 0, 0, 0, 0]).astype(np.bool_),
        oute2=np.array([0, 0, 0, 0, 0, 0]).astype(np.bool_),
        outf2=np.array([0, 0, 0, 0, 0, 0]).astype(np.bool_),
    )
    
    LOGGER.info(f"Setting Panda values: {str(table)}")

    yield from bps.abs_set(panda.seq[1].table, table)

    yield from arm_panda_for_gridscan(panda, wait=True)

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


def arm_panda_for_gridscan(panda: PandA, group="arm_panda_gridscan", wait=False):
    yield from bps.abs_set(panda.seq[1].enable, "ONE", group=group)
    yield from bps.abs_set(panda.pulse[1].enable, "ONE", group=group)
    yield from bps.wait(group="arm_panda_gridscan", timeout=GENERAL_TIMEOUT)
    if wait:
        yield from bps.wait(group=group, timeout=GENERAL_TIMEOUT)


def disarm_panda_for_gridscan(panda, group="disarm_panda_gridscan", wait=False):
    yield from bps.abs_set(panda.seq[1].enable, "ZERO", group=group)
    yield from bps.abs_set(
        panda.clock[1].enable, "ZERO", group=group
    )  # While disarming the clock shouldn't be necessery,
    # it will stop the eiger continuing to trigger if something in the sequencer table goes wrong
    yield from bps.abs_set(panda.pulse[1].enable, "ZERO", group=group)
    yield from bps.wait(group="disarm_panda_gridscan", timeout=GENERAL_TIMEOUT)
    if wait:
        yield from bps.wait(group=group, timeout=GENERAL_TIMEOUT)
