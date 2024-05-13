import gzip
import re
import subprocess
from os import environ
from unittest.mock import patch

import bluesky.preprocessors as bpp
import pytest
from bluesky.run_engine import RunEngine

from hyperion.device_setup_plans.read_hardware_for_setup import (
    read_hardware_for_ispyb_during_collection,
    read_hardware_for_nexus_writer,
)
from hyperion.experiment_plans.rotation_scan_plan import RotationScanComposite
from hyperion.external_interaction.callbacks.rotation.nexus_callback import (
    RotationNexusFileCallback,
)
from hyperion.parameters.constants import CONST
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)

from ...conftest import raw_params_from_file

DOCKER = environ.get("DOCKER", "docker")


@pytest.fixture
def test_params(tmpdir):
    param_dict = raw_params_from_file(
        "tests/test_data/parameter_json_files/good_test_rotation_scan_parameters.json"
    )
    param_dict["hyperion_params"]["detector_params"]["directory"] = "tests/test_data"
    param_dict["experiment_params"]["rotation_angle"] = 360.0
    param_dict["hyperion_params"]["detector_params"]["expected_energy_ev"] = 12700
    param_dict["experiment_params"]["rotation_angle"] = 360.0
    params = RotationInternalParameters(**param_dict)
    params.experiment_params.x = 0
    params.experiment_params.y = 0
    params.experiment_params.z = 0
    params.hyperion_params.detector_params.exposure_time = 0.004
    return params


@pytest.mark.parametrize(
    "test_data_directory, prefix, reference_file",
    [
        (
            "tests/test_data/nexus_files/rotation",
            "ins_8_5",
            "ins_8_5_expected_output.txt",
        ),
        (
            "tests/test_data/nexus_files/rotation_unicode_metafile",
            "ins_8_5",
            "ins_8_5_expected_output.txt",
        ),
    ],
)
@pytest.mark.s03
def test_rotation_nexgen(
    test_params: RotationInternalParameters,
    tmpdir,
    fake_create_rotation_devices: RotationScanComposite,
    test_data_directory,
    prefix,
    reference_file,
):
    meta_file = f"{prefix}_meta.h5.gz"
    test_params.hyperion_params.detector_params.prefix = f"{tmpdir}/{prefix}"
    test_params.hyperion_params.detector_params.directory = f"{tmpdir}"
    run_number = test_params.hyperion_params.detector_params.run_number

    _extract_metafile(
        f"{test_data_directory}/{meta_file}", f"{tmpdir}/{prefix}_{run_number}_meta.h5"
    )

    fake_create_rotation_devices.eiger.bit_depth.sim_put(32)  # type: ignore

    RE = RunEngine({})

    with patch(
        "hyperion.external_interaction.nexus.write_nexus.get_start_and_predicted_end_time",
        return_value=("test_time", "test_time"),
    ):
        RE(
            _fake_rotation_scan(
                test_params, RotationNexusFileCallback(), fake_create_rotation_devices
            )
        )

    master_file = f"{tmpdir}/{prefix}_{run_number}_master.h5"
    _check_nexgen_output_passes_imginfo(
        master_file, f"{test_data_directory}/{reference_file}"
    )


FILE_PATTERN = re.compile("^ ################# File = (.*)")

HEADER_PATTERN = re.compile("^ ===== Header information:")

DATE_PATTERN = re.compile("^ date                                = (.*)")


def _check_nexgen_output_passes_imginfo(test_file, reference_file):
    stdout, stderr = _run_imginfo(test_file)
    assert stderr == ""
    it_actual_lines = iter(stdout.split("\n"))
    i = 0
    try:
        with open(reference_file, "r") as f:
            while True:
                i += 1
                expected_line = f.readline().rstrip("\n")
                actual_line = next(it_actual_lines)
                if FILE_PATTERN.match(actual_line):
                    continue
                if HEADER_PATTERN.match(actual_line):
                    break
                assert (
                    actual_line == expected_line
                ), f"Header line {i} didn't match contents of {reference_file}: {actual_line} <-> {expected_line}"

            while True:
                i += 1
                expected_line = f.readline().rstrip("\n")
                actual_line = next(it_actual_lines)
                if DATE_PATTERN.match(actual_line):
                    continue
                assert (
                    actual_line == expected_line
                ), f"Header line {i} didn't match contents of {reference_file}: {actual_line} <-> {expected_line}"

    except StopIteration:
        pass

        # assert stdout == expected


def _extract_metafile(input_filename, output_filename):
    with gzip.open(input_filename) as metafile_fo:
        with open(output_filename, "wb") as output_fo:
            output_fo.write(metafile_fo.read())


def _run_imginfo(filename):
    process = subprocess.run(
        ["utility_scripts/run_imginfo.sh", filename], text=True, capture_output=True
    )
    assert process.returncode != 2, "imginfo is not available"
    assert (
        process.returncode == 0
    ), f"imginfo failed with returncode {process.returncode}"

    return process.stdout, process.stderr


def _fake_rotation_scan(
    parameters: RotationInternalParameters,
    subscription: RotationNexusFileCallback,
    rotation_devices: RotationScanComposite,
):
    @bpp.subs_decorator(subscription)
    @bpp.set_run_key_decorator("rotation_scan_with_cleanup_and_subs")
    @bpp.run_decorator(  # attach experiment metadata to the start document
        md={
            "subplan_name": CONST.PLAN.ROTATION_OUTER,
            "hyperion_internal_parameters": parameters.json(),
            "activate_callbacks": "RotationNexusFileCallback",
        }
    )
    def plan():
        yield from read_hardware_for_ispyb_during_collection(
            rotation_devices.attenuator, rotation_devices.flux, rotation_devices.dcm
        )
        yield from read_hardware_for_nexus_writer(rotation_devices.eiger)

    return plan()