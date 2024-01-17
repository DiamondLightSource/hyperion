import bluesky.plan_stubs as bps
import numpy as np
from blueapi.core import MsgGenerator
from dodal.devices.panda_fast_grid_scan import PandAGridScanParams
from ophyd_async.core import load_device
from ophyd_async.panda import PandA, SeqTable, SeqTrigger

from hyperion.log import LOGGER

MM_TO_ENCODER_COUNTS = 200000
GENERAL_TIMEOUT = 60
DETECTOR_TRIGGER_WIDTH = 1e-8


def get_seq_table(
    parameters: PandAGridScanParams, time_between_x_steps_ms, exposure_time_s
) -> SeqTable:
    """

    -Setting a 'signal' means trigger PCAP internally and send signal to Eiger via physical panda output
    -When we wait for the position to be greater/lower, give some safe distance (X_STEP_SIZE/2 * MM_TO_ENCODER counts) as the encoder counts arent always exact
    SEQUENCER TABLE:
        1:Wait for physical trigger from motion script to mark start of scan / change of direction
        2:Wait for POSA (X2) to be greater than X_START, then
            send a signal out every (minimum eiger exposure time + eiger dead time)
        3:Wait for POSA (X2) to be greater than X_START + X_STEP_SIZE + a bit of leeway for the final trigger, then cut out the signal
        4:Wait for physical trigger from motion script to mark change of direction
        5:Wait for POSA (X2) to be less than X_START + X_STEP_SIZE + EXPOSURE_DISTANCE, then
            send a signal out every (minimum eiger exposure time + eiger dead time)
        6:Wait for POSA (X2) to be less than (X_START - some leeway + EXPOSURE_DISTANCE), then cut out signal
        7:Go back to step one.

        For a more detailed explanation and a diagram, see https://github.com/DiamondLightSource/hyperion/wiki/PandA-constant%E2%80%90motion-scanning
    """

    sample_velocity_mm_per_s = parameters.x_step_size * 1e-3 / time_between_x_steps_ms

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
                    * MM_TO_ENCODER_COUNTS
                    + (MM_TO_ENCODER_COUNTS * (parameters.x_step_size / 2))
                ),
                0,
                (parameters.x_start * MM_TO_ENCODER_COUNTS)
                + (
                    parameters.x_step_size
                    * (parameters.x_steps - 1)
                    * MM_TO_ENCODER_COUNTS
                    + (
                        sample_velocity_mm_per_s
                        * exposure_time_s
                        * MM_TO_ENCODER_COUNTS
                    )
                ),
                (
                    parameters.x_start * MM_TO_ENCODER_COUNTS
                    - (MM_TO_ENCODER_COUNTS * (parameters.x_step_size / 2))
                    + (
                        sample_velocity_mm_per_s
                        * exposure_time_s
                        * MM_TO_ENCODER_COUNTS
                    )
                ),
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
    return table


def setup_panda_for_flyscan(
    panda: PandA,
    config_yaml_path: str,
    parameters: PandAGridScanParams,
    initial_x: float,
    exposure_time_s: float,
    time_between_x_steps_ms: float,
) -> MsgGenerator:
    """This should load a 'base' panda-flyscan yaml file, then set the
    specific grid parameters, then adjust the PandAsequencer table to match this new grid
    """
    yield from load_device(panda, config_yaml_path)

    yield from bps.abs_set(
        panda.inenc[1].setp, initial_x * MM_TO_ENCODER_COUNTS, wait=True  # type: ignore
    )
    LOGGER.info(
        f"Initialising panda to {initial_x} mm, {initial_x * MM_TO_ENCODER_COUNTS} counts"
    )

    yield from bps.abs_set(panda.clock[1].period, time_between_x_steps_ms)  # type: ignore

    # The trigger width should last the same length as the exposure time
    yield from bps.abs_set(panda.pulse[1].width, DETECTOR_TRIGGER_WIDTH)

    table = get_seq_table(parameters, time_between_x_steps_ms, exposure_time_s)

    LOGGER.info(f"Setting Panda sequencer values: {str(table)}")

    yield from bps.abs_set(panda.seq[1].table, table)

    yield from arm_panda_for_gridscan(panda)


def arm_panda_for_gridscan(panda: PandA, group="arm_panda_gridscan"):
    yield from bps.abs_set(panda.seq[1].enable, "ONE", group=group)  # type: ignore
    yield from bps.abs_set(panda.pulse[1].enable, "ONE", group=group)  # type: ignore
    yield from bps.wait(group=group, timeout=GENERAL_TIMEOUT)


def disarm_panda_for_gridscan(panda, group="disarm_panda_gridscan") -> MsgGenerator:
    yield from bps.abs_set(panda.seq[1].enable, "ZERO", group=group)
    yield from bps.abs_set(
        panda.clock[1].enable, "ZERO", group=group
    )  # While disarming the clock shouldn't be necessery,
    # it will stop the eiger continuing to trigger if something in the sequencer table goes wrong
    yield from bps.abs_set(panda.pulse[1].enable, "ZERO", group=group)
    yield from bps.wait(group=group, timeout=GENERAL_TIMEOUT)
