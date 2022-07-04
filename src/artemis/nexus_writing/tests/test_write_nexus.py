import os
import tempfile
from collections import namedtuple

import h5py
import pytest
from src.artemis.nexus_writing.write_nexus import NexusWriter
from src.artemis.parameters import FullParameters

"""It's hard to effectively unit test the nexus writing so these are really system tests 
that confirms that we're passing the right sorts of data to nexgen to get a sensible output."""

ParamsAndNexusWriter = namedtuple("ParamsAndNexusWriter", ["params", "nexus_writer"])


def get_minimum_parameters_for_file_writing() -> FullParameters:
    test_full_params = FullParameters()
    test_full_params.ispyb_params.wavelength = 1.0
    test_full_params.ispyb_params.flux = 9.0
    test_full_params.ispyb_params.transmission = 0.5
    test_full_params.detector_params.prefix = "file_name"
    return test_full_params


def assert_start_data_correct(params_and_nexus_writer: ParamsAndNexusWriter):
    test_full_params, nexus_writer = params_and_nexus_writer
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


def create_nexus_writer_with_temp_file(test_params: FullParameters) -> NexusWriter:
    nexus_writer = NexusWriter(test_params)
    nexus_writer.nexus_file = tempfile.NamedTemporaryFile(delete=False)
    nexus_writer.master_file = tempfile.NamedTemporaryFile(delete=False)
    return nexus_writer


@pytest.fixture
def params_and_nexus_writer():
    test_full_params = get_minimum_parameters_for_file_writing()
    nexus_writer = create_nexus_writer_with_temp_file(test_full_params)
    return ParamsAndNexusWriter(test_full_params, nexus_writer)


def test_given_full_params_when_enter_called_then_files_written_as_expected(
    params_and_nexus_writer,
):
    params_and_nexus_writer.nexus_writer.__enter__()

    assert_start_data_correct(params_and_nexus_writer)


def test_given_full_params_and_nexus_file_with_entry_when_exit_called_then_end_time_written_to_file(
    params_and_nexus_writer,
):
    nexus_writer = params_and_nexus_writer.nexus_writer

    for file in [nexus_writer.nexus_file, nexus_writer.master_file]:
        with h5py.File(file, "r+") as written_nexus_file:
            written_nexus_file.require_group("entry")

    nexus_writer.__exit__()

    assert_end_data_correct(nexus_writer)


def test_given_parameters_when_nexus_writer_used_as_context_manager_then_all_data_in_file(
    params_and_nexus_writer,
):
    nexus_writer = params_and_nexus_writer.nexus_writer
    with nexus_writer:
        pass

    assert_start_data_correct(params_and_nexus_writer)
    assert_end_data_correct(nexus_writer)


@pytest.mark.parametrize(
    "num_images, expected_num_of_files",
    [(2540, 3), (4000, 4), (8999, 9)],
)
def test_given_number_of_images_above_1000_then_expected_datafiles_used(
    num_images, expected_num_of_files
):
    params = FullParameters()
    params.detector_params.num_images = num_images
    nexus_writer = NexusWriter(params)
    assert len(nexus_writer.get_image_datafiles()) == expected_num_of_files
    paths = [str(filename) for filename in nexus_writer.get_image_datafiles()]
    expected_paths = [
        f"/tmp/file_name_0_00000{i + 1}.h5" for i in range(expected_num_of_files)
    ]
    assert paths == expected_paths


@pytest.fixture
def dummy_nexus_writer():
    params = FullParameters()
    params.detector_params.use_roi_mode = True
    params.detector_params.num_images = 1044
    params.detector_params.directory = (
        os.path.dirname(os.path.realpath(__file__)) + "/test_data"
    )
    params.detector_params.prefix = "dummy"
    nexus_writer = NexusWriter(params)

    yield nexus_writer

    os.remove(nexus_writer.nexus_file)
    os.remove(nexus_writer.master_file)


def test_given_dummy_data_then_datafile_written_correctly(dummy_nexus_writer):
    dummy_nexus_writer.__enter__()

    with h5py.File(dummy_nexus_writer.nexus_file) as f:
        assert f["entry"]["data"]["data"][1043, 0, 0] == 0

        with pytest.raises(IndexError):
            assert f["entry"]["data"]["data"][1044, 0, 0] == 0


def test_nexus_writer_files_are_formatted_as_expected():
    nexus_writer = NexusWriter(get_minimum_parameters_for_file_writing())

    for file in [nexus_writer.nexus_file, nexus_writer.master_file]:
        file_name = os.path.basename(file.name)
        assert file_name.startswith("file_name_0")
