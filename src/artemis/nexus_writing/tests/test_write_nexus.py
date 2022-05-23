import tempfile

import h5py
import pytest
from src.artemis.nexus_writing.write_nexus import NexusWriter
from src.artemis.parameters import FullParameters

"""It's hard to effectively unit test the nexus writing so these are really system tests 
that confirms that we're passing the right sorts of data to nexgen to get a sensible output."""


def get_minimum_parameters_for_file_writing() -> FullParameters:
    test_full_params = FullParameters()
    test_full_params.ispyb_params.wavelength = 1.0
    test_full_params.ispyb_params.flux = 9.0
    test_full_params.ispyb_params.transmission = 0.5
    return test_full_params


def assert_start_data_correct(
    nexus_writer: NexusWriter, test_full_params: FullParameters
):
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


def test_given_full_params_when_enter_called_then_files_written_as_expected():
    test_full_params = get_minimum_parameters_for_file_writing()
    nexus_writer = create_nexus_writer_with_temp_file(test_full_params)
    nexus_writer.__enter__()

    assert_start_data_correct(nexus_writer, test_full_params)


def test_given_full_params_and_nexus_file_with_entry_when_exit_called_then_end_time_written_to_file():
    test_full_params = get_minimum_parameters_for_file_writing()
    nexus_writer = create_nexus_writer_with_temp_file(test_full_params)

    for file in [nexus_writer.nexus_file, nexus_writer.master_file]:
        with h5py.File(file, "r+") as written_nexus_file:
            written_nexus_file.require_group("entry")

    nexus_writer.__exit__()

    assert_end_data_correct(nexus_writer)


def test_given_parameters_when_nexus_writer_used_as_context_manager_then_all_data_in_file():
    test_full_params = get_minimum_parameters_for_file_writing()
    nexus_writer = create_nexus_writer_with_temp_file(test_full_params)
    with nexus_writer:
        pass

    assert_start_data_correct(nexus_writer, test_full_params)
    assert_end_data_correct(nexus_writer)


def test_given_2540_images_then_expected_datafiles_used():
    params = FullParameters()
    params.detector_params.num_images = 2540
    nexus_writer = NexusWriter(params)
    assert len(nexus_writer.get_image_datafiles()) == 3
    paths = [str(filename) for filename in nexus_writer.get_image_datafiles()]
    assert paths == [
        "/tmp/file_name_000001.h5",
        "/tmp/file_name_000002.h5",
        "/tmp/file_name_000003.h5",
    ]
