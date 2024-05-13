import json
import os
import shutil
from pathlib import Path
from unittest.mock import patch

import bluesky.preprocessors as bpp
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

TEST_EXAMPLE_NEXUS_FILE = Path("ins_8_5.nxs")
TEST_DATA_DIRECTORY = Path("tests/test_data")
TEST_FILENAME = "rotation_scan_test_nexus"


def test_params():
    def get_params(filename):
        with open(filename) as f:
            return json.loads(f.read())

    param_dict = get_params(
        "tests/test_data/parameter_json_files/good_test_rotation_scan_parameters.json"
    )

    param_dict["hyperion_params"]["detector_params"]["directory"] = "tests/test_data"
    param_dict["hyperion_params"]["detector_params"]["prefix"] = f"/{TEST_FILENAME}"
    param_dict["experiment_params"]["rotation_angle"] = 360.0
    param_dict["hyperion_params"]["detector_params"]["expected_energy_ev"] = 12700
    param_dict["experiment_params"]["rotation_angle"] = 360.0
    params = RotationInternalParameters(**param_dict)
    params.experiment_params.x = 0
    params.experiment_params.y = 0
    params.experiment_params.z = 0
    params.hyperion_params.detector_params.exposure_time = 0.004
    return params


def fake_rotation_scan(
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


def test_rotation_scan_nexus_output_compared_to_existing_file(
    test_params: RotationInternalParameters,
    tmpdir,
    fake_create_rotation_devices: RotationScanComposite,
):
    run_number = test_params.hyperion_params.detector_params.run_number
    nexus_filename = f"{tmpdir}/{TEST_FILENAME}_{run_number}.nxs"
    master_filename = f"{tmpdir}/{TEST_FILENAME}_{run_number}_master.h5"

    fake_create_rotation_devices.eiger.bit_depth.sim_put(32)  # type: ignore

    RE = RunEngine({})

    with patch(
        "hyperion.external_interaction.nexus.write_nexus.get_start_and_predicted_end_time",
        return_value=("test_time", "test_time"),
    ):
        RE(
            fake_rotation_scan(
                test_params, RotationNexusFileCallback(), fake_create_rotation_devices
            )
        )

    assert os.path.isfile(nexus_filename)
    assert os.path.isfile(master_filename)


def generate_test_nexus_files():
    shutil.copy(TEST_DATA_DIRECTORY / TEST_EXAMPLE_NEXUS_FILE, "GDA_TEST_NEXUS.nxs")
