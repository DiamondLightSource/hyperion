from enum import Enum

import bluesky.plan_stubs as bps
from blueapi.core import MsgGenerator
from dodal.devices.panda_fast_grid_scan import PandAGridScanParams
from ophyd_async.core import load_device
from ophyd_async.panda import (
    PandA,
    SeqTable,
    SeqTableRow,
    SeqTrigger,
    seq_table_from_rows,
)

from hyperion.log import LOGGER

MM_TO_ENCODER_COUNTS = 200000
GENERAL_TIMEOUT = 60
DETECTOR_TRIGGER_WIDTH = 1e-4


class Enabled(Enum):
    ENABLED = "ONE"
    DISABLED = "ZERO"


class PcapArm(Enum):
    ARMED = "Arm"
    DISARMED = "Disarm"


def get_seq_table(
    parameters: PandAGridScanParams,
    exposure_distance_mm,
) -> SeqTable:
    """
    -Exposure distance is the distance travelled by the sample each time the detector is exposed: exposure time * sample velocity
    -Setting a 'signal' means trigger PCAP internally and send signal to Eiger via physical panda output
    -When we wait for the position to be greater/lower, give a safe distance (X_STEP_SIZE/2 * MM_TO_ENCODER counts) to ensure the final trigger point
    is captured
    SEQUENCER TABLE:
        1:Wait for physical trigger from motion script to mark start of scan / change of direction
        2:Wait for POSA (X2) to be greater than X_START, then
            send a signal out every (minimum eiger exposure time + eiger dead time)
        3:Wait for POSA (X2) to be greater than X_START + X_STEP_SIZE + a safe distance for the final trigger, then cut out the signal
        4:Wait for physical trigger from motion script to mark change of direction
        5:Wait for POSA (X2) to be less than X_START + X_STEP_SIZE + exposure distance, then
            send a signal out every (minimum eiger exposure time + eiger dead time)
        6:Wait for POSA (X2) to be less than (X_START - safe distance + exposure distance), then cut out signal
        7:Go back to step one.

        For a more detailed explanation and a diagram, see https://github.com/DiamondLightSource/hyperion/wiki/PandA-constant%E2%80%90motion-scanning
    """

    safe_distance_x_counts = int(MM_TO_ENCODER_COUNTS * parameters.x_step_size / 2)

    start_of_grid_x_counts = int(parameters.x_start * MM_TO_ENCODER_COUNTS)

    # x_start is the first trigger point, so we need to travel to x_steps-1 for the final trigger point
    end_of_grid_x_counts = int(
        start_of_grid_x_counts
        + (parameters.x_step_size * (parameters.x_steps - 1) * MM_TO_ENCODER_COUNTS)
    )

    exposure_distance_x_counts = int(exposure_distance_mm * MM_TO_ENCODER_COUNTS)

    rows = [SeqTableRow(trigger=SeqTrigger.BITA_1, time2=1)]
    rows.append(
        SeqTableRow(
            trigger=SeqTrigger.POSA_GT,
            position=start_of_grid_x_counts,
            time2=1,
            outa1=True,
            outa2=True,
        )
    )
    rows.append(
        SeqTableRow(
            position=end_of_grid_x_counts + safe_distance_x_counts,
            trigger=SeqTrigger.POSA_GT,
            time2=1,
        )
    )

    rows.append(SeqTableRow(trigger=SeqTrigger.BITA_1, time2=1))
    rows.append(
        SeqTableRow(
            trigger=SeqTrigger.POSA_LT,
            position=end_of_grid_x_counts + exposure_distance_x_counts,
            time2=1,
            outa1=True,
            outa2=True,
        )
    )

    rows.append(
        SeqTableRow(
            trigger=SeqTrigger.POSA_LT,
            position=start_of_grid_x_counts
            - safe_distance_x_counts
            + exposure_distance_x_counts,
            time2=1,
        )
    )

    table = seq_table_from_rows(*rows)

    return table


def setup_panda_for_flyscan(
    panda: PandA,
    config_yaml_path: str,
    parameters: PandAGridScanParams,
    initial_x: float,
    exposure_time_s: float,
    time_between_x_steps_ms: float,
    sample_velocity_mm_per_s: float,
) -> MsgGenerator:
    """Configures the PandA device for a flyscan.
    Sets PVs from a yaml file, calibrates the encoder, and
    adjusts the sequencer table based off the grid parameters. Yaml file can be
    created using ophyd_async.core.save_device()

    Args:
        panda (PandA): The PandA Ophyd device
        config_yaml_path (str): Path to the yaml file containing the desired PandA PVs
        parameters (PandAGridScanParams): Grid parameters
        initial_x (float): Motor positions at time of PandA setup
        exposure_time_s (float): Detector exposure time per trigger
        time_between_x_steps_ms (float): Time, in ms, between each trigger. Equal to deadtime + exposure time

    Returns:
        MsgGenerator

    Yields:
        Iterator[MsgGenerator]
    """
    yield from load_device(panda, config_yaml_path)

    # Home the PandA X encoder using current motor position
    yield from bps.abs_set(
        panda.inenc[1].setp, initial_x * MM_TO_ENCODER_COUNTS, wait=True  # type: ignore
    )

    LOGGER.info(f"Setting PandA clock to period {time_between_x_steps_ms}")

    yield from bps.abs_set(panda.clock[1].period, time_between_x_steps_ms, group="panda-config")  # type: ignore

    yield from bps.abs_set(
        panda.pulse[1].width, DETECTOR_TRIGGER_WIDTH, group="panda-config"
    )

    exposure_distance_mm = sample_velocity_mm_per_s * exposure_time_s

    table = get_seq_table(parameters, exposure_distance_mm)

    LOGGER.info(f"Setting PandA sequencer values: {str(table)}")

    yield from bps.abs_set(panda.seq[1].table, table, group="panda-config")

    # Wait here since we need PCAP to be enabled before armed
    yield from bps.abs_set(panda.pcap.enable, Enabled.ENABLED.value, wait=True)  # type: ignore

    yield from arm_panda_for_gridscan(panda, group="panda-config")

    yield from bps.wait(group="panda-config", timeout=GENERAL_TIMEOUT)


def arm_panda_for_gridscan(panda: PandA, group="arm_panda_gridscan"):
    yield from bps.abs_set(panda.seq[1].enable, Enabled.ENABLED.value, group=group)  # type: ignore
    yield from bps.abs_set(panda.pulse[1].enable, Enabled.ENABLED.value, group=group)  # type: ignore
    yield from bps.abs_set(panda.counter[1].enable, Enabled.ENABLED.value, group=group)  # type: ignore
    yield from bps.abs_set(panda.pcap.arm, PcapArm.ARMED.value, group=group)  # type: ignore


def disarm_panda_for_gridscan(panda, group="disarm_panda_gridscan") -> MsgGenerator:
    yield from bps.abs_set(panda.pcap.arm, PcapArm.DISARMED.value, group=group)  # type: ignore
    yield from bps.abs_set(panda.counter[1].enable, Enabled.DISABLED.value, group=group)  # type: ignore
    yield from bps.abs_set(panda.seq[1].enable, Enabled.DISABLED.value, group=group)
    yield from bps.abs_set(
        panda.clock[1].enable, Enabled.DISABLED.value, group=group
    )  # While disarming the clock shouldn't be necessery,
    # it will stop the eiger continuing to trigger if something in the sequencer table goes wrong
    yield from bps.abs_set(panda.pulse[1].enable, Enabled.DISABLED.value, group=group)
    yield from bps.abs_set(panda.pcap.enable, Enabled.DISABLED.value, group=group)  # type: ignore
    yield from bps.wait(group=group, timeout=GENERAL_TIMEOUT)
