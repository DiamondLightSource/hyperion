"""PYTEST_DONT_REWRITE"""

import os
from pathlib import Path
from shutil import copy
from unittest.mock import patch

import bluesky.preprocessors as bpp
import h5py
import numpy as np
import pytest
from bluesky.run_engine import RunEngine
from h5py import Dataset, ExternalLink, Group

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

from ...conftest import extract_metafile, raw_params_from_file

TEST_EXAMPLE_NEXUS_FILE = Path("ins_8_5.nxs")
TEST_EXAMPLE_NEXUS_METAFILE_PREFIX = "ins_8_5_meta"
TEST_DATA_DIRECTORY = Path("tests/test_data/nexus_files/rotation")
TEST_FILENAME = "rotation_scan_test_nexus"


@pytest.fixture
def test_params(tmpdir):
    param_dict = raw_params_from_file(
        "tests/test_data/parameter_json_files/good_test_rotation_scan_parameters.json"
    )
    param_dict["hyperion_params"]["detector_params"]["directory"] = "tests/test_data"
    param_dict["hyperion_params"]["detector_params"][
        "prefix"
    ] = f"{tmpdir}/{TEST_FILENAME}"
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


def test_rotation_scan_nexus_output_compared_to_existing_full_compare(
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

    example_metafile_path = (
        f"{TEST_DATA_DIRECTORY}/{TEST_EXAMPLE_NEXUS_METAFILE_PREFIX}.h5.gz"
    )
    extract_metafile(
        example_metafile_path, f"{tmpdir}/{TEST_EXAMPLE_NEXUS_METAFILE_PREFIX}.h5"
    )
    example_nexus_path = f"{tmpdir}/{TEST_EXAMPLE_NEXUS_FILE}"
    copy(TEST_DATA_DIRECTORY / TEST_EXAMPLE_NEXUS_FILE, example_nexus_path)
    with (
        h5py.File(example_nexus_path, "r") as example_nexus,
        h5py.File(nexus_filename, "r") as hyperion_nexus,
    ):
        _compare_actual_and_expected_nexus_output(
            hyperion_nexus,
            example_nexus,
            {
                "entry": {
                    "_missing": {"end_time"},
                    "_extra": {"source", "end_time_estimated"},
                    "data": {"_ignore": {"data", "omega"}},
                    "instrument": {
                        "_missing": {"transformations", "detector_z", "source"},
                        "detector": {
                            "_missing": {"detector_distance"},
                            "threshold_energy": 1,
                            "detector_readout_time": 1,
                            "distance": 1,
                            "transformations": 1,
                            "detector_z": 1,
                            "underload_value": 1,
                            "bit_depth_image": 1,
                            "_ignore": {
                                "beam_center_x",
                                "beam_center_y",
                                "depends_on",
                                "saturation_value",
                                "sensor_material",
                                "serial_number",
                            },
                            "detectorSpecific": {
                                "_missing": {"pixel_mask"},
                                "eiger_fw_version": 1,
                                "x_pixels": 1,
                                "ntrigger": 1,
                                "data_collection_date": 1,
                                "y_pixels": 1,
                                "software_version": 1,
                            },
                            "module": {"_ignore": {"module_offset"}},
                            "sensor_thickness": np.isclose,
                        },
                        "attenuator": {"_ignore": {"attenuator_transmission"}},
                        "beam": {"_ignore": {"incident_wavelength"}},
                        "name": b"DIAMOND BEAMLINE S03",
                    },
                    "sample": {
                        "beam": {"incident_wavelength": np.isclose},
                        "transformations": {
                            "_missing": {"omega_end", "omega_increment_set"}
                        },
                        "sample_omega": {"omega_end": 1, "omega_increment_set": 1},
                    },
                    "end_time_estimated": b"test_timeZ",
                    "start_time": b"test_timeZ",
                    "source": 1,
                }
            },
        )


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

    with (
        h5py.File(
            str(TEST_DATA_DIRECTORY / TEST_EXAMPLE_NEXUS_FILE), "r"
        ) as example_nexus,
        h5py.File(nexus_filename, "r") as hyperion_nexus,
    ):
        assert hyperion_nexus["/entry/start_time"][()] == b"test_timeZ"  # type: ignore
        assert hyperion_nexus["/entry/end_time_estimated"][()] == b"test_timeZ"  # type: ignore

        # we used to write the positions wrong...
        hyperion_omega: np.ndarray = np.array(
            hyperion_nexus["/entry/data/omega"][:]  # type: ignore
        ) * (3599 / 3600)
        example_omega: np.ndarray = example_nexus["/entry/data/omega"][:]  # type: ignore
        assert np.allclose(hyperion_omega, example_omega)

        assert isinstance(
            hyperion_data := hyperion_nexus["/entry/data/data"], h5py.Dataset
        )
        example_data_shape = example_nexus["/entry/data/data"].shape  # type: ignore

        assert hyperion_data.dtype == "uint32"
        assert hyperion_data.shape == example_data_shape

        hyperion_instrument = hyperion_nexus["/entry/instrument"]
        example_instrument = example_nexus["/entry/instrument"]
        transmission = "attenuator/attenuator_transmission"
        wavelength = "beam/incident_wavelength"
        assert np.isclose(
            hyperion_instrument[transmission][()],  # type: ignore
            example_instrument[transmission][()],  # type: ignore
        )
        assert np.isclose(
            hyperion_instrument[wavelength][()],  # type: ignore
            example_instrument[wavelength][()],  # type: ignore
        )

        hyperion_sam_x = hyperion_nexus["/entry/sample/sample_x/sam_x"]
        example_sam_x = example_nexus["/entry/sample/sample_x/sam_x"]
        hyperion_sam_y = hyperion_nexus["/entry/sample/sample_y/sam_y"]
        example_sam_y = example_nexus["/entry/sample/sample_y/sam_y"]
        hyperion_sam_z = hyperion_nexus["/entry/sample/sample_z/sam_z"]
        example_sam_z = example_nexus["/entry/sample/sample_z/sam_z"]

        hyperion_sam_phi = hyperion_nexus["/entry/sample/sample_phi/phi"]
        example_sam_phi = example_nexus["/entry/sample/sample_phi/phi"]
        hyperion_sam_chi = hyperion_nexus["/entry/sample/sample_chi/chi"]
        example_sam_chi = example_nexus["/entry/sample/sample_chi/chi"]

        hyperion_sam_omega = hyperion_nexus["/entry/sample/sample_omega/omega"]
        example_sam_omega = example_nexus["/entry/sample/sample_omega/omega"]

        assert np.isclose(
            hyperion_sam_x[()],  # type: ignore
            example_sam_x[()],  # type: ignore
        )
        assert np.isclose(
            hyperion_sam_y[()],  # type: ignore
            example_sam_y[()],  # type: ignore
        )
        assert np.isclose(
            hyperion_sam_z[()],  # type: ignore
            example_sam_z[()],  # type: ignore
        )

        assert hyperion_sam_x.attrs.get("depends_on") == example_sam_x.attrs.get(
            "depends_on"
        )
        assert hyperion_sam_y.attrs.get("depends_on") == example_sam_y.attrs.get(
            "depends_on"
        )
        assert hyperion_sam_z.attrs.get("depends_on") == example_sam_z.attrs.get(
            "depends_on"
        )
        assert hyperion_sam_phi.attrs.get("depends_on") == example_sam_phi.attrs.get(
            "depends_on"
        )
        assert hyperion_sam_chi.attrs.get("depends_on") == example_sam_chi.attrs.get(
            "depends_on"
        )
        assert hyperion_sam_omega.attrs.get(
            "depends_on"
        ) == example_sam_omega.attrs.get("depends_on")


@pytest.mark.parametrize(
    "bit_depth,expected_type",
    [(8, np.uint8), (16, np.uint16), (32, np.uint32), (100, np.uint16)],
)
@patch("hyperion.external_interaction.nexus.write_nexus.NXmxFileWriter")
def test_given_detector_bit_depth_changes_then_vds_datatype_as_expected(
    mock_nexus_writer,
    test_params: RotationInternalParameters,
    fake_create_rotation_devices: RotationScanComposite,
    bit_depth,
    expected_type,
):
    write_vds_mock = mock_nexus_writer.return_value.write_vds

    fake_create_rotation_devices.eiger.bit_depth.sim_put(bit_depth)  # type: ignore

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

        for call in write_vds_mock.mock_calls:
            assert call.kwargs["vds_dtype"] == expected_type


def _compare_actual_and_expected_nexus_output(actual, expected, exceptions: dict):
    _compare_actual_and_expected([], actual, expected, exceptions)


def _compare_actual_and_expected(path: list[str], actual, expected, exceptions: dict):
    path_str = "/".join(path)
    print(f"Comparing {path_str}")
    keys_not_in_actual = (
        expected.keys() - actual.keys() - exceptions.get("_missing", set())
    )
    assert (
        len(keys_not_in_actual) == 0
    ), f"Missing entries in group {path_str}, {keys_not_in_actual}"

    keys_to_compare = actual.keys()
    keys_not_in_expected = (
        keys_to_compare
        - expected.keys()
        - {k for k in exceptions.keys() if not k.startswith("_")}
    )
    cmp = len(keys_not_in_expected) == 0
    keys_to_compare = sorted(keys_to_compare)
    assert cmp, f"Found unexpected entries in group {path_str}, {keys_not_in_expected}"
    for key in keys_to_compare:
        item_path = path + [key]
        actual_link = actual.get(key, getlink=True)
        item_path_str = "/" + "/".join(item_path)
        if isinstance(actual_link, ExternalLink):
            print(f"Skipping external link {item_path_str}")
            continue
        actual_class = actual.get(key, getclass=True, getlink=False)
        expected_class = expected.get(key, getclass=True)
        actual_value = actual.get(key)
        expected_value = expected.get(key)
        if expected_class == Group:
            _compare_actual_and_expected(
                item_path, actual_value, expected_value, exceptions.get(key, {})
            )
        elif expected_class == Dataset and key not in exceptions.get("_ignore", set()):
            assert (
                actual_value.shape == expected_value.shape
            ), f"Actual and expected shapes differ for {item_path_str}: {actual_value.shape}, {expected_value.shape}"
            if actual_value.shape == ():
                exception = exceptions.get(key, None)
                if callable(exception):
                    assert exceptions.get(key)(actual_value, expected_value)
                elif np.isscalar(exception):
                    assert actual_value[()] == exception
                else:
                    assert (
                        actual_class == expected_class
                    ), f"{item_path_str} Actual and expected class don't match {actual_class}, {expected_class}"
                    assert (
                        actual_value[()] == expected_value[()]
                    ), f"Actual and expected values differ for {item_path_str}: {actual_value[()]} != {expected_value[()]}"
            else:
                print(f"Ignoring non-scalar value {item_path_str}\n")
