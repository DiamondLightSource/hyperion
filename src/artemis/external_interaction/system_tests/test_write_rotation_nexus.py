import os
from pathlib import Path

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import pytest
from bluesky.run_engine import RunEngine

from artemis.external_interaction.callbacks.rotation.rotation_callback_collection import (
    RotationCallbackCollection,
)
from artemis.parameters.external_parameters import from_file
from artemis.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)

TEST_EXAMPLE_NEXUS_FILE = Path("ins_8_5.nxs")
TEST_DIRECTORY = Path("src/artemis/external_interaction/unit_tests/test_data/")
TEST_FILENAME = "rotation_scan_test_nexus"


@pytest.fixture
def test_params():
    param_dict = from_file(
        "src/artemis/parameters/tests/test_data/good_test_rotation_scan_parameters.json"
    )
    param_dict["artemis_params"]["detector_params"][
        "directory"
    ] = "src/artemis/external_interaction/unit_tests/test_data"
    param_dict["artemis_params"]["detector_params"]["prefix"] = TEST_FILENAME
    params = RotationInternalParameters(**param_dict)
    params.artemis_params.detector_params.exposure_time = 0.004
    params.artemis_params.detector_params.current_energy_ev = 12700
    return params


def fake_get_plan(
    parameters: RotationInternalParameters, subscriptions: RotationCallbackCollection
):
    @bpp.subs_decorator(list(subscriptions))
    @bpp.set_run_key_decorator("run_gridscan_move_and_tidy")
    @bpp.run_decorator(  # attach experiment metadata to the start document
        md={
            "subplan_name": "rotation_scan_with_cleanup",
            "hyperion_internal_parameters": parameters.json(),
        }
    )
    def plan():
        yield from bps.sleep(0)

    return plan()


def test_rotation_scan_nexus_output_compared_to_existing_file(
    test_params: RotationInternalParameters,
):
    run_number = test_params.artemis_params.detector_params.run_number
    nexus_filename = str(TEST_DIRECTORY / (TEST_FILENAME + f"_{run_number}.nxs"))
    master_filename = str(TEST_DIRECTORY / (TEST_FILENAME + f"_{run_number}_master.h5"))

    if os.path.isfile(nexus_filename):
        os.remove(nexus_filename)
    if os.path.isfile(master_filename):
        os.remove(master_filename)

    RE = RunEngine({})

    cb = RotationCallbackCollection.from_params(test_params)

    RE(fake_get_plan(test_params, cb))

    assert os.path.isfile(nexus_filename)
    assert os.path.isfile(master_filename)
