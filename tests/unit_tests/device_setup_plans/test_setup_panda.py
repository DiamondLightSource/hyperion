from datetime import datetime
from typing import NamedTuple
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from bluesky.plan_stubs import null
from bluesky.run_engine import RunEngine
from bluesky.simulators import RunEngineSimulator
from dodal.common.types import UpdatingDirectoryProvider
from dodal.devices.fast_grid_scan import PandAGridScanParams
from ophyd_async.panda import SeqTrigger

from hyperion.device_setup_plans.setup_panda import (
    MM_TO_ENCODER_COUNTS,
    disarm_panda_for_gridscan,
    set_panda_directory,
    setup_panda_for_flyscan,
)


def get_smargon_speed(x_step_size_mm: float, time_between_x_steps_ms: float) -> float:
    return x_step_size_mm / time_between_x_steps_ms


def run_simulating_setup_panda_functions(
    plan: str, sim_run_engine: RunEngineSimulator, mock_load_device=MagicMock
):
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
    sim.add_handler(["set", "wait"], count_commands)

    if plan == "setup":
        smargon_speed = get_smargon_speed(0.1, 1)
        sim.simulate_plan(
            setup_panda_for_flyscan(
                mock_panda,
                PandAGridScanParams(transmission_fraction=0.01),
                1,
                0.1,
                100.1,
                smargon_speed,
            )
        )
    elif plan == "disarm":
        sim.simulate_plan(disarm_panda_for_gridscan(mock_panda))

    return num_of_sets, num_of_waits


@patch("hyperion.device_setup_plans.setup_panda.load_device")
def test_setup_panda_performs_correct_plans(mock_load_device, sim_run_engine):
    num_of_sets, num_of_waits = run_simulating_setup_panda_functions(
        "setup", sim_run_engine, mock_load_device
    )
    mock_load_device.assert_called_once()
    assert num_of_sets == 8
    assert num_of_waits == 3


class SeqRow(NamedTuple):
    repeats: int
    trigger: SeqTrigger
    position: int
    time1: int
    outa1: int
    time2: int
    outa2: int


@pytest.mark.parametrize(
    "x_steps, x_step_size, x_start, run_up_distance_mm, time_between_x_steps_ms, exposure_time_s",
    [
        (10, 0.2, 0, 0.5, 10.001, 0.01),
        (10, 0.5, -1, 0.05, 10.001, 0.01),
        (1, 2, 1.2, 1, 100.001, 0.1),
        (10, 2, -0.5, 3, 101, 0.1),
    ],
)
def test_setup_panda_correctly_configures_table(
    x_steps: int,
    x_step_size: float,
    x_start: float,
    run_up_distance_mm: float,
    time_between_x_steps_ms: float,
    exposure_time_s: float,
    sim_run_engine: RunEngineSimulator,
    panda,
):
    sample_velocity_mm_per_s = get_smargon_speed(x_step_size, time_between_x_steps_ms)
    params = PandAGridScanParams(
        x_steps=x_steps,
        x_step_size=x_step_size,
        x_start=x_start,
        run_up_distance_mm=run_up_distance_mm,
        transmission_fraction=0.01,
    )

    exposure_distance_mm = sample_velocity_mm_per_s * exposure_time_s

    msgs = sim_run_engine.simulate_plan(
        setup_panda_for_flyscan(
            panda,
            params,
            0,
            exposure_time_s,
            time_between_x_steps_ms,
            sample_velocity_mm_per_s,
        )
    )

    # ignore all loading operations related to loading saved panda state from yaml
    msgs = [
        msg for msg in msgs if not msg.kwargs.get("group", "").startswith("load-phase")
    ]

    table_msg = [
        msg
        for msg in msgs
        if msg.command == "set" and msg.obj.name == "panda-seq-1-table"
    ][0]

    table = table_msg.args[0]

    PULSE_WIDTH_US = 1
    SPACE_WIDTH_US = int(time_between_x_steps_ms * 1000 - PULSE_WIDTH_US)
    expected_seq_rows: list[SeqRow] = [
        SeqRow(1, SeqTrigger.BITA_1, 0, 0, 0, 1, 0),
        SeqRow(
            x_steps,
            SeqTrigger.POSA_GT,
            int(params.x_start * MM_TO_ENCODER_COUNTS),
            PULSE_WIDTH_US,
            1,
            SPACE_WIDTH_US,
            0,
        ),
    ]

    exposure_distance_counts = exposure_distance_mm * MM_TO_ENCODER_COUNTS
    expected_seq_rows.extend(
        [
            SeqRow(1, SeqTrigger.BITA_1, 0, 0, 0, 1, 0),
            SeqRow(
                x_steps,
                SeqTrigger.POSA_LT,
                int(
                    (params.x_start + (params.x_steps - 1) * params.x_step_size)
                    * MM_TO_ENCODER_COUNTS
                    + exposure_distance_counts
                ),
                PULSE_WIDTH_US,
                1,
                SPACE_WIDTH_US,
                0,
            ),
        ]
    )

    for key in SeqRow._fields:
        np.testing.assert_array_equal(
            table.get(key),
            [getattr(row, key) for row in expected_seq_rows],
            f"Sequence table for field {key} does not match",
        )


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
                PandAGridScanParams(transmission_fraction=0.01),
                1,
                0.1,
                101.1,
                get_smargon_speed(0.1, 1),
            )
        )


# It also would be useful to have some system tests which check that (at least)
# all the blocks which were enabled on setup are also disabled on tidyup
def test_disarm_panda_disables_correct_blocks(sim_run_engine):
    num_of_sets, num_of_waits = run_simulating_setup_panda_functions(
        "disarm", sim_run_engine
    )
    assert num_of_sets == 5
    assert num_of_waits == 1


@patch("hyperion.device_setup_plans.setup_panda.get_directory_provider")
@patch("hyperion.device_setup_plans.setup_panda.datetime", spec=datetime)
def test_set_panda_directory(
    mock_datetime, mock_get_directory_provider: MagicMock, tmp_path, RE
):
    mock_directory_provider = MagicMock(spec=UpdatingDirectoryProvider)
    mock_datetime.now = MagicMock(
        return_value=datetime.fromisoformat("2024-08-11T15:59:23")
    )
    mock_get_directory_provider.return_value = mock_directory_provider

    RE(set_panda_directory(tmp_path))
    mock_directory_provider.update.assert_called_with(
        directory=tmp_path, suffix="_20240811155923"
    )
