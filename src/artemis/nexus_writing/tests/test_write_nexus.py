import os
from pathlib import Path
from unittest.mock import call, patch

import h5py
import pytest

from artemis.nexus_writing.write_nexus import NexusWriter
from artemis.parameters import FullParameters

"""It's hard to effectively unit test the nexus writing so these are really system tests
that confirms that we're passing the right sorts of data to nexgen to get a sensible output.
Note that the testing process does now write temporary files to disk."""


def assert_start_data_correct(test_full_params, nexus_writer):
    for filename in [nexus_writer.nexus_file, nexus_writer.master_file]:
        with h5py.File(filename, "r") as written_nexus_file:
            sam_x_data = written_nexus_file["/entry/data/sam_x"][:]
            assert len(sam_x_data) == (
                test_full_params.grid_scan_params.x_steps + 1
            ) * (test_full_params.grid_scan_params.y_steps + 1)
            assert sam_x_data[1] - sam_x_data[0] == pytest.approx(
                test_full_params.grid_scan_params.x_step_size
            )
            assert written_nexus_file["/entry/instrument/beam/total_flux"][()] == 9.0


def assert_end_data_correct(nexus_writer: NexusWriter):
    for filename in [nexus_writer.nexus_file, nexus_writer.master_file]:
        with h5py.File(filename, "r") as written_nexus_file:
            assert "end_time" in written_nexus_file["entry"]


@pytest.fixture(params=[1044])
def minimal_params(request):
    params = FullParameters()
    params.ispyb_params.wavelength = 1.0
    params.ispyb_params.flux = 9.0
    params.ispyb_params.transmission = 0.5
    params.detector_params.use_roi_mode = True
    params.detector_params.num_images = request.param
    params.detector_params.directory = (
        os.path.dirname(os.path.realpath(__file__)) + "/test_data"
    )
    params.detector_params.prefix = "dummy"
    yield params


@pytest.fixture
def dummy_nexus_writer(minimal_params):
    nexus_writer = NexusWriter(minimal_params)

    yield nexus_writer

    if os.path.isfile(nexus_writer.nexus_file):
        os.remove(nexus_writer.nexus_file)
    if os.path.isfile(nexus_writer.master_file):
        os.remove(nexus_writer.master_file)


def test_given_full_params_when_enter_called_then_files_written_as_expected(
    minimal_params, dummy_nexus_writer
):
    dummy_nexus_writer.__enter__()

    assert_start_data_correct(minimal_params, dummy_nexus_writer)


def test_given_full_params_and_nexus_file_with_entry_when_exit_called_then_end_time_written_to_file(
    dummy_nexus_writer,
):
    dummy_nexus_writer.__enter__()

    for file in [dummy_nexus_writer.nexus_file, dummy_nexus_writer.master_file]:
        with h5py.File(file, "r+") as written_nexus_file:
            written_nexus_file.require_group("entry")

    dummy_nexus_writer.__exit__()

    assert_end_data_correct(dummy_nexus_writer)


def test_given_parameters_when_nexus_writer_used_as_context_manager_then_all_data_in_file(
    minimal_params,
    dummy_nexus_writer,
):
    with dummy_nexus_writer:
        pass

    assert_start_data_correct(minimal_params, dummy_nexus_writer)
    assert_end_data_correct(dummy_nexus_writer)


@pytest.mark.parametrize(
    "minimal_params, expected_num_of_files",
    [(2540, 3), (4000, 4), (8999, 9)],
    indirect=["minimal_params"],
)
def test_given_number_of_images_above_1000_then_expected_datafiles_used(
    minimal_params, expected_num_of_files, dummy_nexus_writer
):
    assert len(dummy_nexus_writer.get_image_datafiles()) == expected_num_of_files
    paths = [str(filename) for filename in dummy_nexus_writer.get_image_datafiles()]
    expected_paths = [
        f"{os.path.dirname(os.path.realpath(__file__))}/test_data/dummy_0_00000{i + 1}.h5"
        for i in range(expected_num_of_files)
    ]
    assert paths == expected_paths


def test_given_dummy_data_then_datafile_written_correctly(dummy_nexus_writer):
    dummy_nexus_writer.__enter__()

    with h5py.File(dummy_nexus_writer.nexus_file) as f:
        assert f["entry"]["data"]["data"][1043, 0, 0] == 0

        with pytest.raises(IndexError):
            assert f["entry"]["data"]["data"][1044, 0, 0] == 0


def test_nexus_writer_files_are_formatted_as_expected(
    minimal_params, dummy_nexus_writer
):
    for file in [dummy_nexus_writer.nexus_file, dummy_nexus_writer.master_file]:
        file_name = os.path.basename(file.name)
        expected_file_name_prefix = minimal_params.detector_params.prefix + "_0"
        assert file_name.startswith(expected_file_name_prefix)


def test_nexus_writer_opens_temp_file_on_exit(dummy_nexus_writer):
    nexus_file = dummy_nexus_writer.nexus_file
    master_file = dummy_nexus_writer.master_file
    temp_nexus_file = Path(f"{str(nexus_file)}.tmp")
    temp_master_file = Path(f"{str(master_file)}.tmp")
    calls_with_temp = [call(temp_nexus_file, "r+"), call(temp_master_file, "r+")]
    calls_without_temp = [call(nexus_file, "r+"), call(master_file, "r+")]

    dummy_nexus_writer.__enter__()

    with patch("h5py.File") as mock_h5py_file:
        dummy_nexus_writer.__exit__()
        actual_mock_calls = mock_h5py_file.mock_calls
        assert all(call in actual_mock_calls for call in calls_with_temp)
        assert all(call not in actual_mock_calls for call in calls_without_temp)
