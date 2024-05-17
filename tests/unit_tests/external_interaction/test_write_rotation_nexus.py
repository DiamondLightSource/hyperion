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
from hyperion.log import LOGGER
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


def dectris_device_mapping(meta_filename: str):
    return {
        "entry": {
            "instrument": {
                "detector": {
                    "bit_depth_image": f"{meta_filename}//_dectris/bit_depth_image",
                    "bit_depth_readout": f"{meta_filename}//_dectris/bit_depth_image",
                    "detectorSpecific": {
                        "ntrigger": f"{meta_filename}///_dectris/ntrigger",
                        "software_version": f"{meta_filename}//_dectris/software_version",
                    },
                    "detector_readout_time": f"{meta_filename}//_dectris/detector_readout_time",
                    "flatfield_applied": f"{meta_filename}//_dectris/flatfield_correction_applied",
                    "photon_energy": f"{meta_filename}//_dectris/photon_energy",
                    "pixel_mask": f"{meta_filename}//mask",
                    "pixel_mask_applied": f"{meta_filename}//_dectris/pixel_mask_applied",
                    "threshold_energy": f"{meta_filename}//_dectris/threshold_energy",
                }
            }
        }
    }


def apply_metafile_mapping(exceptions: dict, mapping: dict):
    """Recursively populate the exceptions map with corresponding mapping entries"""
    for key in mapping.keys():
        mapping_value = mapping.get(key)
        if isinstance(mapping_value, dict):
            exceptions_child = exceptions.setdefault(key, {})
            apply_metafile_mapping(exceptions_child, mapping_value)
        else:
            exceptions[key] = mapping_value


def test_rotation_scan_nexus_output_compared_to_existing_full_compare(
    test_params: RotationInternalParameters,
    tmpdir,
    fake_create_rotation_devices: RotationScanComposite,
):
    run_number = test_params.hyperion_params.detector_params.run_number
    nexus_filename = f"{tmpdir}/{TEST_FILENAME}_{run_number}.nxs"
    master_filename = f"{tmpdir}/{TEST_FILENAME}_{run_number}_master.h5"
    meta_filename = f"{TEST_FILENAME}_{run_number}_meta.h5"

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

    # Models expected differences to the GDA master nexus file
    # If a key is in _missing then it is not expected to be present
    # If a key is in _ignore then we do not compare it
    # If a key maps to a dict then we expect it to be a Group
    # Otherwise if a key is present we expect it to be a DataSet
    # If a key maps to a callable then we use that as the comparison function
    # Otherwise we compare the scalar or array value as appropriate
    exceptions = {
        "entry": {
            "_missing": {"end_time"},
            "data": {"_ignore": {"data", "omega"}},
            "instrument": {
                "_missing": {"transformations", "detector_z", "source"},
                "detector": {
                    "_missing": {
                        "detector_distance",
                        "serial_number",  # nexgen#236
                    },
                    "distance": 0.1,
                    "transformations": {
                        "detector_z": {"det_z": np.array([100])},
                        "det_z": np.array([100]),
                    },
                    "detector_z": {"det_z": np.array([100])},
                    "underload_value": 0,
                    "_ignore": {
                        "beam_center_x",
                        "beam_center_y",
                        "depends_on",
                        "saturation_value",
                        "sensor_material",
                    },
                    "detectorSpecific": {
                        "_missing": {"pixel_mask"},
                        "x_pixels": 4148,
                        "y_pixels": 4362,
                    },
                    "module": {"_ignore": {"module_offset"}},
                    "sensor_thickness": np.isclose,
                },
                "attenuator": {"attenuator_transmission": np.isclose},
                "beam": {"incident_wavelength": np.isclose},
                "name": b"DIAMOND BEAMLINE S03",
            },
            "sample": {
                "beam": {"incident_wavelength": np.isclose},
                "transformations": {
                    "_missing": {"omega_end"},
                    "_ignore": {"omega"},
                    "omega_increment_set": 0.1,
                    "omega_end": lambda a, b: np.all(np.isclose(a, b, atol=1e-03)),
                },
                "sample_omega": {
                    "_ignore": {"omega_end", "omega"},
                    "omega_increment_set": 0.1,
                },
                "sample_x": {"sam_x": np.isclose},
                "sample_y": {"sam_y": np.isclose},
                "sample_z": {"sam_z": np.isclose},
                "sample_chi": {"chi": np.isclose},
                "sample_phi": {"phi": np.isclose},
            },
            "end_time_estimated": b"test_timeZ",
            "start_time": b"test_timeZ",
            "source": {
                "name": b"Diamond Light Source",
                "type": b"Synchrotron X-ray Source",
            },
        }
    }

    with (
        h5py.File(example_nexus_path, "r") as example_nexus,
        h5py.File(nexus_filename, "r") as hyperion_nexus,
    ):
        apply_metafile_mapping(exceptions, dectris_device_mapping(meta_filename))
        _compare_actual_and_expected_nexus_output(
            hyperion_nexus, example_nexus, exceptions
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
        )
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
    if expected is None:
        # The nexus file under test contains a node that isn't in the original GDA reference nexus file
        # but we may still expect something if the exception map contains it
        expected = {}

    path_str = "/".join(path)
    LOGGER.debug(f"Comparing {path_str}")
    keys_not_in_actual = (
        expected.keys() - actual.keys() - exceptions.get("_missing", set())
    )
    assert (
        len(keys_not_in_actual) == 0
    ), f"Missing entries in group {path_str}, {keys_not_in_actual}"

    keys_to_compare = actual.keys()
    keys_to_ignore = exceptions.get("_ignore", set())
    keys_not_in_expected = (
        keys_to_compare
        - expected.keys()
        - {k for k in exceptions.keys() if not k.startswith("_")}
        - keys_to_ignore
    )
    cmp = len(keys_not_in_expected) == 0
    keys_to_compare = sorted(keys_to_compare)
    assert cmp, f"Found unexpected entries in group {path_str}, {keys_not_in_expected}"
    for key in keys_to_compare:
        item_path = path + [key]
        actual_link = actual.get(key, getlink=True)
        item_path_str = "/" + "/".join(item_path)
        exception = exceptions.get(key, None)
        if isinstance(actual_link, ExternalLink):
            if exception:
                actual_link_path = f"{actual_link.filename}//{actual_link.path}"
                assert (
                    actual_link_path == exception
                ), f"Actual and expected external links differ {actual_link_path}, {exception}"
            else:
                LOGGER.debug(
                    f"Skipping external link {item_path_str} -> {actual_link.path}"
                )
            continue
        actual_class = actual.get(key, getclass=True, getlink=False)
        expected_class = (
            Group
            if isinstance(exception, dict)
            else (
                Dataset if exception is not None else expected.get(key, getclass=True)  # type: ignore
            )
        )
        actual_value = actual.get(key)
        expected_value = (
            expected.get(key)
            if (exception is None or isinstance(exception, dict) or callable(exception))
            else exception
        )
        if expected_class == Group:
            _compare_actual_and_expected(
                item_path, actual_value, expected.get(key), exceptions.get(key, {})
            )
        elif (expected_class == Dataset) and key not in keys_to_ignore:
            if isinstance(expected_value, Dataset):
                # Only check shape if we didn't override the expected value
                assert (
                    actual_value.shape == expected_value.shape
                ), f"Actual and expected shapes differ for {item_path_str}: {actual_value.shape}, {expected_value.shape}"
            else:
                assert hasattr(actual_value, "shape"), f"No shape for {item_path_str}"
                expected_shape = np.shape(expected_value)  # type: ignore
                assert (
                    actual_value.shape == expected_shape
                ), f"{item_path_str} data shape not expected shape{actual_value.shape}, {expected_shape}"
            if actual_value.shape == ():
                if callable(exception):
                    assert exceptions.get(key)(actual_value, expected_value)  # type: ignore
                elif np.isscalar(exception):
                    assert (
                        actual_value[()] == exception
                    ), f"{item_path_str} actual and expected did not match {actual_value[()]}, {exception}."
                else:
                    assert (
                        actual_class == expected_class
                    ), f"{item_path_str} Actual and expected class don't match {actual_class}, {expected_class}"
                    assert (
                        actual_value[()] == expected_value[()]  # type: ignore
                    ), f"Actual and expected values differ for {item_path_str}: {actual_value[()]} != {expected_value[()]}"  # type: ignore
            else:
                actual_value_str = np.array2string(actual_value, threshold=10)
                expected_value_str = np.array2string(expected_value, threshold=10)  # type: ignore
                if callable(exception):
                    assert exception(
                        actual_value, expected_value
                    ), f"Actual and expected values differ for {item_path_str}: {actual_value_str} != {expected_value_str}"
                else:
                    assert np.array_equal(
                        actual_value,
                        expected_value,  # type: ignore
                    ), f"Actual and expected values differ for {item_path_str}: {actual_value_str} != {expected_value_str}"
