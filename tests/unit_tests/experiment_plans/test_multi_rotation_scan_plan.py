from __future__ import annotations

import json
from itertools import takewhile
from typing import Any, Callable, Sequence
from unittest.mock import MagicMock, patch

from bluesky.run_engine import RunEngine
from dodal.devices.synchrotron import SynchrotronMode
from ophyd_async.core import set_mock_value

from hyperion.experiment_plans.rotation_scan_plan import (
    RotationScanComposite,
    calculate_motion_profile,
    multi_rotation_scan,
)
from hyperion.external_interaction.callbacks.rotation.nexus_callback import (
    RotationNexusFileCallback,
)
from hyperion.parameters.rotation import MultiRotationScan, RotationScan

from ...conftest import CallbackSim, RunEngineSimulator, raw_params_from_file
from .conftest import fake_read

TEST_OFFSET = 1
TEST_SHUTTER_OPENING_DEGREES = 2.5


def test_multi_rotation_scan_params():
    raw_params = raw_params_from_file(
        "tests/test_data/parameter_json_files/good_test_multi_rotation_scan_parameters.json"
    )
    params = MultiRotationScan(**raw_params)
    omega_starts = [s["omega_start_deg"] for s in raw_params["rotation_scans"]]
    for i, scan in enumerate(params.single_rotation_scans):
        assert scan.omega_start_deg == omega_starts[i]
        assert scan.nexus_vds_start_img == params.scan_indices[i]
        assert params.scan_indices


def test_multi_rotation_plan_runs_multiple_plans_in_one_arm(
    fake_create_rotation_devices: RotationScanComposite,
    test_multi_rotation_params: MultiRotationScan,
    sim_run_engine_for_rotation: RunEngineSimulator,
):
    omega = fake_create_rotation_devices.smargon.omega
    set_mock_value(
        fake_create_rotation_devices.synchrotron.synchrotron_mode, SynchrotronMode.USER
    )
    msgs = sim_run_engine_for_rotation.simulate_plan(
        multi_rotation_scan(fake_create_rotation_devices, test_multi_rotation_params)
    )

    msgs = sim_run_engine_for_rotation.assert_message_and_return_remaining(
        msgs, lambda msg: msg.command == "stage" and msg.obj.name == "eiger"
    )[1:]

    msgs_within_arming = list(
        takewhile(
            lambda msg: msg.command != "unstage"
            and (not msg.obj or msg.obj.name != "eiger"),
            msgs,
        )
    )

    def _assert_set_seq_and_return_remaining(remaining, name_value_pairs):
        for name, value in name_value_pairs:
            try:
                remaining = (
                    sim_run_engine_for_rotation.assert_message_and_return_remaining(
                        remaining,
                        lambda msg: msg.command == "set"
                        and msg.obj.name == name
                        and msg.args == (value,),
                    )
                )
            except Exception as e:
                raise Exception(f"Failed to find {name} being set to {value}") from e
        return remaining

    for scan in test_multi_rotation_params.single_rotation_scans:
        motion_values = calculate_motion_profile(
            scan, int(omega.acceleration.get()), int(omega.max_velocity.get())
        )
        # moving to the start position
        msgs_within_arming = _assert_set_seq_and_return_remaining(
            msgs_within_arming,
            [
                ("smargon_x", scan.x_start_um),
                ("smargon_y", scan.y_start_um),
                ("smargon_z", scan.z_start_um),
                ("smargon_phi", scan.phi_start_deg),
                ("smargon_chi", scan.chi_start_deg),
            ],
        )
        # arming the zebra
        msgs_within_arming = (
            sim_run_engine_for_rotation.assert_message_and_return_remaining(
                msgs_within_arming,
                lambda msg: msg.command == "set" and msg.obj.name == "zebra-pc-arm",
            )
        )
        # the final rel_set of omega to trigger the scan
        sim_run_engine_for_rotation.assert_message_and_return_remaining(
            msgs_within_arming,
            lambda msg: msg.command == "set"
            and msg.obj.name == "smargon_omega"
            and msg.args
            == (
                (scan.scan_width_deg + motion_values.shutter_opening_deg)
                * motion_values.direction.multiplier,
            ),
        )


def _run_multi_rotation_plan(
    RE: RunEngine,
    params: MultiRotationScan,
    devices: RotationScanComposite,
    callbacks: Sequence[Callable[[str, dict[str, Any]], Any]],
):
    for cb in callbacks:
        RE.subscribe(cb)
    with patch("bluesky.preprocessors.__read_and_stash_a_motor", fake_read):
        RE(multi_rotation_scan(devices, params))


def test_full_multi_rotation_plan_docs_emitted(
    RE: RunEngine,
    test_multi_rotation_params: MultiRotationScan,
    fake_create_rotation_devices: RotationScanComposite,
):
    callback_sim = CallbackSim()
    _run_multi_rotation_plan(
        RE, test_multi_rotation_params, fake_create_rotation_devices, [callback_sim]
    )
    docs = callback_sim.docs_recieved

    assert (
        outer_plan_start_doc := CallbackSim.assert_doc(
            docs, "start", matches_fields=({"plan_name": "multi_rotation_scan"})
        )
    )
    outer_uid = outer_plan_start_doc[1]["uid"]
    inner_run_docs = CallbackSim.get_docs_until(
        docs,
        "stop",
        matches_fields=({"run_start": outer_uid, "exit_status": "success"}),
    )[1:-1]

    for scan in test_multi_rotation_params.single_rotation_scans:
        inner_run_docs = CallbackSim.get_docs_from(
            inner_run_docs,
            "start",
            matches_fields={"subplan_name": "rotation_scan_with_cleanup"},
        )
        scan_docs = CallbackSim.get_docs_until(
            inner_run_docs,
            "stop",
            matches_fields={"run_start": inner_run_docs[0][1]["uid"]},
        )
        assert CallbackSim.is_match(
            scan_docs[0],
            "start",
            has_fields=["trigger_zocalo_on", "hyperion_parameters"],
        )
        params = RotationScan(**json.loads(scan_docs[0][1]["hyperion_parameters"]))
        assert params == scan
        assert len(events := CallbackSim.get_matches(scan_docs, "event")) == 4
        CallbackSim.assert_events_and_data_in_order(
            events,
            [
                ["eiger_odin_file_writer_id"],
                ["undulator-current_gap", "synchrotron-synchrotron_mode", "smargon_x"],
                [
                    "attenuator-actual_transmission",
                    "flux_flux_reading",
                    "dcm-energy_in_kev",
                ],
                ["eiger_bit_depth"],
            ],
        )
        inner_run_docs = CallbackSim.get_docs_from(
            inner_run_docs,
            "stop",
            matches_fields={"run_start": inner_run_docs[0][1]["uid"]},
        )


@patch("hyperion.external_interaction.callbacks.rotation.nexus_callback.NexusWriter")
def test_full_multi_rotation_plan_nexus_writer_called_correctly(
    mock_nexus_writer: MagicMock,
    RE: RunEngine,
    test_multi_rotation_params: MultiRotationScan,
    fake_create_rotation_devices: RotationScanComposite,
):
    callback = RotationNexusFileCallback()
    _run_multi_rotation_plan(
        RE, test_multi_rotation_params, fake_create_rotation_devices, [callback]
    )
    nexus_writer_calls = mock_nexus_writer.call_args_list
    first_run_number = test_multi_rotation_params.detector_params.run_number
    for call, rotation_params in zip(
        nexus_writer_calls, test_multi_rotation_params.single_rotation_scans
    ):
        assert call.args[0] == rotation_params
        assert call.kwargs == {
            "omega_start_deg": rotation_params.omega_start_deg,
            "chi_start_deg": rotation_params.chi_start_deg,
            "phi_start_deg": rotation_params.phi_start_deg,
            "vds_start_index": rotation_params.nexus_vds_start_img,
            "full_num_of_images": test_multi_rotation_params.num_images,
            "meta_data_run_number": first_run_number,
        }
