from __future__ import annotations

import json
import shutil
from itertools import takewhile
from math import ceil
from typing import Any, Callable, Sequence
from unittest.mock import MagicMock, patch

import h5py
import numpy as np
import pytest
from bluesky.run_engine import RunEngine
from dodal.devices.synchrotron import SynchrotronMode
from ophyd_async.core import set_mock_value

from hyperion.experiment_plans.rotation_scan_plan import (
    RotationScanComposite,
    calculate_motion_profile,
    multi_rotation_scan,
)
from hyperion.external_interaction.callbacks.rotation.ispyb_callback import (
    RotationISPyBCallback,
)
from hyperion.external_interaction.callbacks.rotation.nexus_callback import (
    RotationNexusFileCallback,
)
from hyperion.external_interaction.ispyb.ispyb_store import StoreInIspyb
from hyperion.parameters.constants import CONST
from hyperion.parameters.rotation import MultiRotationScan, RotationScan

from ...conftest import (
    CallbackSim,
    RunEngineSimulator,
    extract_metafile,
    fake_read,
    raw_params_from_file,
)

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
            "rotation_direction": rotation_params.rotation_direction,
        }


def test_full_multi_rotation_plan_nexus_files_written_correctly(
    RE: RunEngine,
    test_multi_rotation_params: MultiRotationScan,
    fake_create_rotation_devices: RotationScanComposite,
    tmpdir,
):
    multi_params = test_multi_rotation_params
    prefix = "multi_rotation_test"
    test_data_dir = "tests/test_data/nexus_files/"
    meta_file = f"{test_data_dir}rotation/ins_8_5_meta.h5.gz"
    fake_datafile = f"{test_data_dir}fake_data.h5"
    multi_params.file_name = prefix
    multi_params.storage_directory = f"{tmpdir}"
    meta_data_run_number = multi_params.detector_params.run_number

    data_filename_prefix = f"{prefix}_{meta_data_run_number}_"
    meta_filename = f"{prefix}_{meta_data_run_number}_meta.h5"

    callback = RotationNexusFileCallback()
    _run_multi_rotation_plan(RE, multi_params, fake_create_rotation_devices, [callback])

    def _expected_dset_number(image_number: int):
        # image numbers 0-999 are in dset 1, etc.
        return int(ceil((image_number + 1) / 1000))

    num_datasets = range(
        1, _expected_dset_number(multi_params.num_images - 1)
    )  # the index of the last image is num_images - 1

    for i in num_datasets:
        shutil.copy(
            fake_datafile,
            f"{tmpdir}/{data_filename_prefix}{i:06d}.h5",
        )
    extract_metafile(
        meta_file,
        f"{tmpdir}/{meta_filename}",
    )
    for i, scan in enumerate(multi_params.single_rotation_scans):
        with h5py.File(f"{tmpdir}/{prefix}_{i+1}.nxs", "r") as written_nexus_file:
            # check links go to the right file:
            detector_specific = written_nexus_file[
                "entry/instrument/detector/detectorSpecific"
            ]
            for field in ["software_version"]:
                link = detector_specific.get(field, getlink=True)  # type: ignore
                assert link.filename == meta_filename  # type: ignore
            data_group = written_nexus_file["entry/data"]
            for field in [f"data_{n:06d}" for n in num_datasets]:
                link = data_group.get(field, getlink=True)  # type: ignore
                assert link.filename.startswith(data_filename_prefix)  # type: ignore

            # check dataset starts and stops are correct:
            assert isinstance(dataset := data_group["data"], h5py.Dataset)  # type: ignore
            assert dataset.is_virtual
            assert dataset[scan.num_images - 1, 0, 0] == 0
            with pytest.raises(IndexError):
                assert dataset[scan.num_images, 0, 0] == 0
            dataset_sources = dataset.virtual_sources()
            expected_dset_start = _expected_dset_number(multi_params.scan_indices[i])
            expected_dset_end = _expected_dset_number(multi_params.scan_indices[i + 1])
            dset_start_name = dataset_sources[0].dset_name
            dset_end_name = dataset_sources[-1].dset_name
            assert dset_start_name.endswith(f"data_{expected_dset_start:06d}")
            assert dset_end_name.endswith(f"data_{expected_dset_end:06d}")

            # check scan values are correct for each file:
            assert isinstance(
                chi := written_nexus_file["/entry/sample/sample_chi/chi"], h5py.Dataset
            )
            assert chi[:] == scan.chi_start_deg
            assert isinstance(
                phi := written_nexus_file["/entry/sample/sample_phi/phi"], h5py.Dataset
            )
            assert phi[:] == scan.phi_start_deg
            assert isinstance(
                omega := written_nexus_file["/entry/sample/sample_omega/omega"],
                h5py.Dataset,
            )
            omega = omega[:]
            assert isinstance(
                omega_end := written_nexus_file["/entry/sample/sample_omega/omega_end"],
                h5py.Dataset,
            )
            omega_end = omega_end[:]
            assert len(omega) == scan.num_images
            expected_omega_starts = np.linspace(
                scan.omega_start_deg,
                scan.omega_start_deg
                + ((scan.num_images - 1) * multi_params.rotation_increment_deg),
                scan.num_images,
            )
            assert np.allclose(omega, expected_omega_starts)
            expected_omega_ends = (
                expected_omega_starts + multi_params.rotation_increment_deg
            )
            assert np.allclose(omega_end, expected_omega_ends)
            assert isinstance(
                omega_transform := written_nexus_file[
                    "/entry/sample/transformations/omega"
                ],
                h5py.Dataset,
            )
            assert isinstance(omega_vec := omega_transform.attrs["vector"], np.ndarray)
            assert tuple(omega_vec) == (1.0 * scan.rotation_direction.multiplier, 0, 0)


@patch("hyperion.external_interaction.callbacks.rotation.ispyb_callback.StoreInIspyb")
def test_full_multi_rotation_plan_ispyb_called_correctly(
    mock_ispyb_store: MagicMock,
    RE: RunEngine,
    test_multi_rotation_params: MultiRotationScan,
    fake_create_rotation_devices: RotationScanComposite,
):
    callback = RotationISPyBCallback()
    mock_ispyb_store.return_value = MagicMock(spec=StoreInIspyb)
    _run_multi_rotation_plan(
        RE, test_multi_rotation_params, fake_create_rotation_devices, [callback]
    )
    ispyb_calls = mock_ispyb_store.call_args_list
    first_run_number = test_multi_rotation_params.detector_params.run_number
    for instantiation_call, ispyb_store_calls, rotation_params in zip(
        ispyb_calls,
        [  # there should be 4 calls to the IspybStore per run
            mock_ispyb_store.return_value.method_calls[i * 4 : (i + 1) * 4]
            for i in range(len(test_multi_rotation_params.rotation_scans))
        ],
        test_multi_rotation_params.single_rotation_scans,
    ):
        assert instantiation_call.args[0] == CONST.SIM.ISPYB_CONFIG
        assert ispyb_store_calls[0][0] == "begin_deposition"
        assert ispyb_store_calls[1][0] == "update_deposition"
        assert ispyb_store_calls[2][0] == "update_deposition"
        assert ispyb_store_calls[3][0] == "end_deposition"
