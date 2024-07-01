from __future__ import annotations

import shutil
from math import ceil
from typing import Any, Callable, Sequence
from unittest.mock import patch

import h5py
import pytest
from bluesky.run_engine import RunEngine

from hyperion.experiment_plans.rotation_scan_plan import (
    RotationScanComposite,
    multi_rotation_scan,
)
from hyperion.external_interaction.callbacks.rotation.nexus_callback import (
    RotationNexusFileCallback,
)
from hyperion.parameters.rotation import MultiRotationScan

from ....conftest import extract_metafile, fake_read


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


@pytest.mark.s03
def test_full_multi_rotation_plan_nexus_files_written_correctly(
    RE: RunEngine,
    test_multi_rotation_params: MultiRotationScan,
    fake_create_rotation_devices: RotationScanComposite,
    tmpdir,
):
    prefix = "multi_rotation_test"
    test_data_dir = "tests/test_data/nexus_files/"
    meta_file = f"{test_data_dir}rotation/ins_8_5_meta.h5.gz"
    fake_datafile = f"{test_data_dir}fake_data.h5"
    test_multi_rotation_params.file_name = prefix
    test_multi_rotation_params.storage_directory = f"{tmpdir}"
    meta_data_run_number = test_multi_rotation_params.detector_params.run_number

    data_filename_prefix = f"{prefix}_{meta_data_run_number}_00000"
    meta_filename = f"{prefix}_{meta_data_run_number}_meta.h5"

    callback = RotationNexusFileCallback()
    _run_multi_rotation_plan(
        RE, test_multi_rotation_params, fake_create_rotation_devices, [callback]
    )

    num_datasets = range(1, int(ceil(test_multi_rotation_params.num_images / 1000)) + 1)
    for i in num_datasets:
        shutil.copy(
            fake_datafile,
            f"{tmpdir}/{data_filename_prefix}{i}.h5",
        )
    extract_metafile(
        meta_file,
        f"{tmpdir}/{meta_filename}",
    )
    for i, scan in enumerate(test_multi_rotation_params.single_rotation_scans):
        with h5py.File(f"{tmpdir}/{prefix}_{i+1}.nxs", "r") as written_nexus_file:
            detector_specific = written_nexus_file[
                "entry/instrument/detector/detectorSpecific"
            ]
            for field in ["software_version"]:
                link = detector_specific.get(field, getlink=True)  # type: ignore
                assert link.filename == meta_filename  # type: ignore
            data = written_nexus_file["entry/data"]
            for field in [f"data_00000{i}" for i in num_datasets]:
                link = data.get(field, getlink=True)  # type: ignore
                assert link.filename.startswith(data_filename_prefix)  # type: ignore
