from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from bluesky.plan_stubs import null
from bluesky.run_engine import RunEngine
from dodal.devices.panda_fast_grid_scan import PandAGridScanParams
from ophyd_async.panda import SeqTrigger

from hyperion.device_setup_plans.setup_panda import (
    MM_TO_ENCODER_COUNTS,
    disarm_panda_for_gridscan,
    get_seq_table,
    set_and_create_panda_directory,
    setup_panda_for_flyscan,
)

from ...conftest import RunEngineSimulator


def get_smargon_speed(x_step_size_mm: float, time_between_x_steps_ms: float) -> float:
    return x_step_size_mm / time_between_x_steps_ms


def run_simulating_setup_panda_functions(plan: str, mock_load_device=MagicMock):
    num_of_sets = 0
    num_of_waits = 0
    mock_panda = MagicMock()

    def count_commands(msg):
        nonlocal num_of_sets
        nonlocal num_of_waits
        if msg.command == "set":
            num_of_sets += 1
        elif msg.command == "wait":
            num_of_waits += 1

    sim = RunEngineSimulator()
    sim.add_handler(
        ["set", "wait"],
        None,
        count_commands,
    )

    if plan == "setup":
        smargon_speed = get_smargon_speed(0.1, 1)
        sim.simulate_plan(
            setup_panda_for_flyscan(
                mock_panda,
                "path",
                PandAGridScanParams(transmission_fraction=0.01),
                1,
                1,
                1,
                smargon_speed,
            )
        )
    elif plan == "disarm":
        sim.simulate_plan(disarm_panda_for_gridscan(mock_panda))

    return num_of_sets, num_of_waits


@patch("hyperion.device_setup_plans.setup_panda.load_device")
def test_setup_panda_performs_correct_plans(mock_load_device):
    num_of_sets, num_of_waits = run_simulating_setup_panda_functions(
        "setup", mock_load_device
    )
    mock_load_device.assert_called_once()
    assert num_of_sets == 9
    assert num_of_waits == 3


@pytest.mark.parametrize(
    "x_steps, x_step_size, x_start, run_up_distance_mm, time_between_x_steps_ms, exposure_time_s",
    [
        (10, 0.5, -1, 0.05, 10, 0.02),
        (0, 5, 0, 1, 1, 0.02),
        (1, 2, 1.2, 1, 10, 0.1),
    ],
)
def test_setup_panda_correctly_configures_table(
    x_steps: int,
    x_step_size: float,
    x_start: float,
    run_up_distance_mm: float,
    time_between_x_steps_ms: float,
    exposure_time_s: float,
):
    """The table should satisfy the following requirements:
    -All the numpy arrays within the Seqtable should have a length of 6

    -The position array should correspond to the following logic:
        1.Wait for physical trigger
        2.Wait for POSA > x_start
        3.Wait for end of row
        4.Wait for physical trigger (end of direction)
        5.Wait for POSA to go below the end of the row
        6.Wait for POSA to go below X_start

    -Time1 should be a 0 array, since we don't use the first phase in any of our panda logic
    -Time2 should be a length 6 array all set to 1, so that each of the 6 steps run as quickly as possible

    -We want to send triggers between step 2 and 3, and between step 4 and 5, so we want the outa2 array
    to look like [0,1,0,0,1,0]
    """

    sample_velocity_mm_per_s = get_smargon_speed(x_step_size, time_between_x_steps_ms)
    params = PandAGridScanParams(
        x_steps=x_steps,
        x_step_size=x_step_size,
        x_start=x_start,
        run_up_distance_mm=run_up_distance_mm,
        transmission_fraction=0.01,
    )

    exposure_distance_mm = int(sample_velocity_mm_per_s * exposure_time_s)

    table = get_seq_table(params, exposure_distance_mm)

    np.testing.assert_array_equal(table["time2"], np.ones(6))

    safe_distance = int((params.x_step_size * MM_TO_ENCODER_COUNTS) / 2)

    exposure_distance_counts = exposure_distance_mm * MM_TO_ENCODER_COUNTS

    np.testing.assert_array_equal(
        table["position"],
        np.array(
            [
                0,
                params.x_start * MM_TO_ENCODER_COUNTS,
                (params.x_start + (params.x_steps - 1) * params.x_step_size)
                * MM_TO_ENCODER_COUNTS
                + safe_distance,
                0,
                (params.x_start + (params.x_steps - 1) * params.x_step_size)
                * MM_TO_ENCODER_COUNTS
                + exposure_distance_counts,
                params.x_start * MM_TO_ENCODER_COUNTS
                - safe_distance
                + exposure_distance_counts,
            ],
            dtype=np.int32,
        ),
    )

    np.testing.assert_array_equal(
        table["trigger"],
        np.array(
            [
                SeqTrigger.BITA_1,
                SeqTrigger.POSA_GT,
                SeqTrigger.POSA_GT,
                SeqTrigger.BITA_1,
                SeqTrigger.POSA_LT,
                SeqTrigger.POSA_LT,
            ]
        ),
    )

    np.testing.assert_array_equal(table["outa2"], np.array([0, 1, 0, 0, 1, 0]))


def test_wait_between_setting_table_and_arming_panda(RE: RunEngine):
    bps_wait_done = False

    def handle_wait(*args, **kwargs):
        nonlocal bps_wait_done
        bps_wait_done = True
        yield from null()

    def assert_set_table_has_been_waited_on(*args, **kwargs):
        assert bps_wait_done
        yield from null()

    with patch(
        "hyperion.device_setup_plans.setup_panda.arm_panda_for_gridscan",
        MagicMock(side_effect=assert_set_table_has_been_waited_on),
    ), patch(
        "hyperion.device_setup_plans.setup_panda.bps.wait",
        MagicMock(side_effect=handle_wait),
    ), patch(
        "hyperion.device_setup_plans.setup_panda.load_device"
    ), patch(
        "hyperion.device_setup_plans.setup_panda.bps.abs_set"
    ):
        RE(
            setup_panda_for_flyscan(
                MagicMock(),
                "path",
                PandAGridScanParams(transmission_fraction=0.01),
                1,
                1,
                1,
                get_smargon_speed(0.1, 1),
            )
        )


# It also would be useful to have some system tests which check that (at least)
# all the blocks which were enabled on setup are also disabled on tidyup
def test_disarm_panda_disables_correct_blocks():
    num_of_sets, num_of_waits = run_simulating_setup_panda_functions("disarm")
    assert num_of_sets == 6
    assert num_of_waits == 1


def test_set_and_create_panda_directory(tmp_path):
    with patch(
        "hyperion.device_setup_plans.setup_panda.os.path.isdir", return_value=False
    ), patch("hyperion.device_setup_plans.setup_panda.os.makedirs") as mock_makedir:
        set_and_create_panda_directory(Path(tmp_path))
        mock_makedir.assert_called_once()

    with patch(
        "hyperion.device_setup_plans.setup_panda.os.path.isdir", return_value=True
    ), patch("hyperion.device_setup_plans.setup_panda.os.makedirs") as mock_makedir:
        set_and_create_panda_directory(Path(tmp_path))
        mock_makedir.assert_not_called()
