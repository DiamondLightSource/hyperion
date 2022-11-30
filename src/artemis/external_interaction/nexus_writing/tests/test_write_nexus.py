import os
import sys
from pathlib import Path
from unittest.mock import call, patch

import dlstbx.swmr.h5check
import h5py
import numpy as np
import pytest

from artemis.devices.fast_grid_scan import GridAxis, GridScanParams
from artemis.external_interaction.nexus_writing.write_nexus import (
    NexusWriter,
    create_parameters_for_first_file,
    create_parameters_for_second_file,
)
from artemis.parameters import FullParameters

"""It's hard to effectively unit test the nexus writing so these are really system tests
that confirms that we're passing the right sorts of data to nexgen to get a sensible output.
Note that the testing process does now write temporary files to disk."""


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
def dummy_nexus_writers(minimal_params):
    first_file_params = create_parameters_for_first_file(minimal_params)
    nexus_writer_1 = NexusWriter(first_file_params)

    second_file_params = create_parameters_for_second_file(minimal_params)
    nexus_writer_2 = NexusWriter(second_file_params)

    yield nexus_writer_1, nexus_writer_2

    for writer in [nexus_writer_1, nexus_writer_2]:
        os.remove(writer.nexus_file)
        os.remove(writer.master_file)


@pytest.fixture
def single_dummy_file(minimal_params):
    nexus_writer = NexusWriter(minimal_params)
    yield nexus_writer
    for file in [nexus_writer.nexus_file, nexus_writer.master_file]:
        if os.path.isfile(file):
            os.remove(file)


@pytest.mark.parametrize(
    "minimal_params, expected_num_of_files",
    [(2540, 3), (4000, 4), (8999, 9)],
    indirect=["minimal_params"],
)
def test_given_number_of_images_above_1000_then_expected_datafiles_used(
    minimal_params, expected_num_of_files, single_dummy_file
):
    first_writer = single_dummy_file
    assert len(first_writer.get_image_datafiles()) == expected_num_of_files
    paths = [str(filename) for filename in first_writer.get_image_datafiles()]
    expected_paths = [
        f"{os.path.dirname(os.path.realpath(__file__))}/test_data/dummy_0_00000{i + 1}.h5"
        for i in range(expected_num_of_files)
    ]
    assert paths == expected_paths


def test_given_dummy_data_then_datafile_written_correctly(
    minimal_params, dummy_nexus_writers: tuple[NexusWriter, NexusWriter]
):
    nexus_writer_1, nexus_writer_2 = dummy_nexus_writers
    grid_scan_params: GridScanParams = minimal_params.grid_scan_params
    nexus_writer_1.create_nexus_file()

    for filename in [nexus_writer_1.nexus_file, nexus_writer_1.master_file]:
        with h5py.File(filename, "r") as written_nexus_file:
            data_path = written_nexus_file["/entry/data"]
            assert_x_data_stride_correct(
                data_path, grid_scan_params, grid_scan_params.y_steps
            )
            assert_varying_axis_stride_correct(
                data_path["sam_y"][:], grid_scan_params, grid_scan_params.y_axis
            )
            assert_axis_data_fixed(written_nexus_file, "z", grid_scan_params.z1_start)
            assert written_nexus_file["/entry/instrument/beam/total_flux"][()] == 9.0
            assert_contains_external_link(data_path, "data_000001", "dummy_0_000001.h5")
            assert "data_000002" not in data_path
            assert np.all(data_path["omega"][:] == 0.0)

            assert np.all(
                written_nexus_file["/entry/data/omega"].attrs.get("vector")
                == [
                    -1.0,
                    0.0,
                    0.0,
                ]
            )
            assert np.all(
                written_nexus_file["/entry/data/sam_x"].attrs.get("vector")
                == [
                    1.0,
                    0.0,
                    0.0,
                ]
            )
            assert np.all(
                written_nexus_file["/entry/data/sam_y"].attrs.get("vector")
                == [
                    0.0,
                    1.0,
                    0.0,
                ]
            )

    assert_data_edge_at(nexus_writer_1.nexus_file, 799)

    nexus_writer_1.update_nexus_file_timestamp()
    assert_end_data_correct(nexus_writer_1)

    nexus_writer_2.create_nexus_file()

    for filename in [nexus_writer_2.nexus_file, nexus_writer_2.master_file]:
        with h5py.File(filename, "r") as written_nexus_file:
            data_path = written_nexus_file["/entry/data"]
            assert_x_data_stride_correct(
                data_path, grid_scan_params, grid_scan_params.z_steps
            )
            assert_varying_axis_stride_correct(
                data_path["sam_z"][:], grid_scan_params, grid_scan_params.z_axis
            )
            assert_axis_data_fixed(written_nexus_file, "y", grid_scan_params.y2_start)
            assert written_nexus_file["/entry/instrument/beam/total_flux"][()] == 9.0
            assert_contains_external_link(data_path, "data_000001", "dummy_0_000001.h5")
            assert_contains_external_link(data_path, "data_000002", "dummy_0_000002.h5")
            assert np.all(data_path["omega"][:] == 90.0)
            assert np.all(
                written_nexus_file["/entry/data/sam_z"].attrs.get("vector")
                == [
                    0.0,
                    0.0,
                    1.0,
                ]
            )

    assert_data_edge_at(nexus_writer_2.nexus_file, 243)


def assert_x_data_stride_correct(data_path, grid_scan_params, varying_axis_steps):
    sam_x_data = data_path["sam_x"][:]
    assert len(sam_x_data) == (grid_scan_params.x_steps + 1) * (varying_axis_steps + 1)
    assert sam_x_data[1] - sam_x_data[0] == pytest.approx(grid_scan_params.x_step_size)


def assert_varying_axis_stride_correct(
    axis_data, grid_scan_params: GridScanParams, varying_axis: GridAxis
):
    assert len(axis_data) == (grid_scan_params.x_steps + 1) * (
        varying_axis.full_steps + 1
    )
    assert axis_data[grid_scan_params.x_steps + 1] - axis_data[0] == pytest.approx(
        varying_axis.step_size
    )


def assert_axis_data_fixed(written_nexus_file, axis, expected_value):
    assert f"sam_{axis}" not in written_nexus_file["/entry/data"]
    sam_y_data = written_nexus_file[f"/entry/sample/sample_{axis}/sam_{axis}"][()]
    assert sam_y_data == expected_value


def assert_data_edge_at(nexus_file, expected_edge_index):
    """Asserts that the datafile's last datapoint is at the specified index"""
    with h5py.File(nexus_file) as f:
        assert f["entry"]["data"]["data"][expected_edge_index, 0, 0] == 0

        with pytest.raises(IndexError):
            assert f["entry"]["data"]["data"][expected_edge_index + 1, 0, 0] == 0


def assert_contains_external_link(data_path, entry_name, file_name):
    assert entry_name in data_path
    assert data_path[entry_name].file.filename.endswith(file_name)


def test_nexus_writer_files_are_formatted_as_expected(
    minimal_params: FullParameters, single_dummy_file: NexusWriter
):
    for file in [single_dummy_file.nexus_file, single_dummy_file.master_file]:
        file_name = os.path.basename(file.name)
        expected_file_name_prefix = minimal_params.detector_params.prefix + "_0"
        assert file_name.startswith(expected_file_name_prefix)


def test_nexus_writer_opens_temp_file_on_exit(single_dummy_file: NexusWriter):
    nexus_file = single_dummy_file.nexus_file
    master_file = single_dummy_file.master_file
    temp_nexus_file = Path(f"{str(nexus_file)}.tmp")
    temp_master_file = Path(f"{str(master_file)}.tmp")
    calls_with_temp = [call(temp_nexus_file, "r+"), call(temp_master_file, "r+")]
    calls_without_temp = [call(nexus_file, "r+"), call(master_file, "r+")]

    single_dummy_file.create_nexus_file()

    with patch("h5py.File") as mock_h5py_file:
        single_dummy_file.update_nexus_file_timestamp()
        actual_mock_calls = mock_h5py_file.mock_calls
        assert all(call in actual_mock_calls for call in calls_with_temp)
        assert all(call not in actual_mock_calls for call in calls_without_temp)


def test_nexus_writer_writes_width_and_height_correctly(single_dummy_file):
    from artemis.devices.det_dim_constants import (
        PIXELS_X_EIGER2_X_4M,
        PIXELS_Y_EIGER2_X_4M,
    )

    assert single_dummy_file.detector["image_size"][0] == PIXELS_Y_EIGER2_X_4M
    assert single_dummy_file.detector["image_size"][1] == PIXELS_X_EIGER2_X_4M


def test_nexus_file_validity_for_zocalo(
    dummy_nexus_writers: tuple[NexusWriter, NexusWriter]
):
    nexus_writer_1, nexus_writer_2 = dummy_nexus_writers

    nexus_writer_1.create_nexus_file()
    nexus_writer_2.create_nexus_file()

    for filename in [nexus_writer_1.nexus_file, nexus_writer_1.master_file]:
        with h5py.File(filename, "r") as written_nexus_file:
            dlstbx.swmr.h5check.get_real_frames(
                written_nexus_file, written_nexus_file["entry/data/data"]
            )

    for filename in [nexus_writer_2.nexus_file, nexus_writer_2.master_file]:
        with h5py.File(filename, "r") as written_nexus_file:
            dlstbx.swmr.h5check.get_real_frames(
                written_nexus_file, written_nexus_file["entry/data/data"]
            )
