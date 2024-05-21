import os
from contextlib import contextmanager
from typing import Literal
from unittest.mock import patch

import h5py
import numpy as np
import pytest
from dodal.devices.detector.det_dim_constants import (
    PIXELS_X_EIGER2_X_4M,
    PIXELS_Y_EIGER2_X_4M,
)
from dodal.devices.fast_grid_scan import GridAxis, GridScanParams

from hyperion.external_interaction.nexus.nexus_utils import (
    create_beam_and_attenuator_parameters,
)
from hyperion.external_interaction.nexus.write_nexus import NexusWriter
from hyperion.parameters.gridscan import ThreeDGridScan

"""It's hard to effectively unit test the nexus writing so these are really system tests
that confirms that we're passing the right sorts of data to nexgen to get a sensible output.
Note that the testing process does now write temporary files to disk."""

TEST_FLUX = 1e10


def assert_end_data_correct(nexus_writer: NexusWriter):
    for filename in [nexus_writer.nexus_file, nexus_writer.master_file]:
        with h5py.File(filename, "r") as written_nexus_file:
            entry = written_nexus_file["entry"]
            assert isinstance(entry, h5py.Group)
            assert "end_time_estimated" in entry


def create_nexus_writer(parameters: ThreeDGridScan, writer_num):
    d_size = parameters.detector_params.detector_size_constants.det_size_pixels
    n_img = (
        parameters.scan_indices[1]
        if writer_num == 1
        else parameters.num_images - parameters.scan_indices[1]
    )
    points = parameters.scan_points_1 if writer_num == 1 else parameters.scan_points_2
    data_shape = (n_img, d_size.width, d_size.height)
    run_number = parameters.detector_params.run_number + writer_num - 1
    vds_start = 0 if writer_num == 1 else parameters.scan_indices[1]
    omega_start = (
        parameters.grid1_omega_deg if writer_num == 1 else parameters.grid2_omega_deg
    )
    nexus_writer = NexusWriter(
        parameters,
        data_shape,
        scan_points=points,
        run_number=run_number,
        vds_start_index=vds_start,
        omega_start_deg=omega_start,
    )
    nexus_writer.beam, nexus_writer.attenuator = create_beam_and_attenuator_parameters(
        20, TEST_FLUX, 0.5
    )
    return nexus_writer


@contextmanager
def create_nexus_writers(parameters: ThreeDGridScan):
    writers = [create_nexus_writer(parameters, i) for i in [1, 2]]
    writers[1].start_index = parameters.scan_indices[1]
    try:
        yield writers
    finally:
        for writer in writers:
            for file in [writer.nexus_file, writer.master_file]:
                if os.path.isfile(file):
                    os.remove(file)


@pytest.fixture
def dummy_nexus_writers(test_fgs_params: ThreeDGridScan):
    with create_nexus_writers(test_fgs_params) as (
        nexus_writer_1,
        nexus_writer_2,
    ):
        yield nexus_writer_1, nexus_writer_2


@pytest.fixture
def dummy_nexus_writers_with_more_images(test_fgs_params: ThreeDGridScan):
    x, y, z = 45, 35, 25
    test_fgs_params.x_steps = x
    test_fgs_params.y_steps = y
    test_fgs_params.z_steps = z
    with create_nexus_writers(test_fgs_params) as (
        nexus_writer_1,
        nexus_writer_2,
    ):
        yield nexus_writer_1, nexus_writer_2


@pytest.fixture
def single_dummy_file(test_fgs_params: ThreeDGridScan):
    test_fgs_params.use_roi_mode = True
    d_size = test_fgs_params.detector_params.detector_size_constants.det_size_pixels
    data_shape = (test_fgs_params.scan_indices[1], d_size.width, d_size.height)
    nexus_writer = NexusWriter(
        test_fgs_params,
        data_shape,
        scan_points=test_fgs_params.scan_points_1,
        run_number=1,
    )
    yield nexus_writer
    for file in [nexus_writer.nexus_file, nexus_writer.master_file]:
        if os.path.isfile(file):
            os.remove(file)


@pytest.mark.parametrize(
    "test_fgs_params, expected_num_of_files",
    [(2550, 3), (4000, 4), (8975, 9)],
    indirect=["test_fgs_params"],
)
def test_given_number_of_images_above_1000_then_expected_datafiles_used(
    test_fgs_params: ThreeDGridScan,
    expected_num_of_files: Literal[3, 4, 9],
    single_dummy_file: NexusWriter,
):
    datafiles = single_dummy_file.get_image_datafiles()
    assert len(datafiles) == expected_num_of_files
    paths = [str(filename) for filename in datafiles]
    test_data_folder = (
        os.path.dirname(os.path.realpath(os.path.join(__file__, ".."))) + "/test_data"
    )
    expected_paths = [
        f"{test_data_folder}/dummy_1_00000{i + 1}.h5"
        for i in range(expected_num_of_files)
    ]
    assert expected_paths[0] == paths[0]


def test_given_dummy_data_then_datafile_written_correctly(
    test_fgs_params: ThreeDGridScan,
    dummy_nexus_writers: tuple[NexusWriter, NexusWriter],
):
    nexus_writer_1, nexus_writer_2 = dummy_nexus_writers
    grid_scan_params: GridScanParams = test_fgs_params.FGS_params
    nexus_writer_1.create_nexus_file(np.uint16)

    for filename in [nexus_writer_1.nexus_file, nexus_writer_1.master_file]:
        with h5py.File(filename, "r") as written_nexus_file:
            assert isinstance(
                data_path := written_nexus_file["/entry/data"], h5py.Group
            )
            assert_x_data_stride_correct(
                data_path, grid_scan_params, grid_scan_params.y_steps
            )
            assert isinstance(sam_y := data_path["sam_y"], h5py.Dataset)
            assert_varying_axis_stride_correct(
                sam_y[:], grid_scan_params, grid_scan_params.y_axis
            )
            assert_axis_data_fixed(written_nexus_file, "z", grid_scan_params.z1_start)
            assert isinstance(
                flux := written_nexus_file["/entry/instrument/beam/total_flux"],
                h5py.Dataset,
            )
            assert flux[()] == TEST_FLUX
            assert_contains_external_link(data_path, "data_000001", "dummy_1_000001.h5")
            assert isinstance(omega := data_path["omega"], h5py.Dataset)
            assert np.all(omega[:] == 0.0)

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

    assert_data_edge_at(nexus_writer_1.nexus_file, 629)
    assert_end_data_correct(nexus_writer_1)

    nexus_writer_2.create_nexus_file(np.uint16)

    for filename in [nexus_writer_2.nexus_file, nexus_writer_2.master_file]:
        with h5py.File(filename, "r") as written_nexus_file:
            assert isinstance(
                data_path := written_nexus_file["/entry/data"], h5py.Group
            )
            assert_x_data_stride_correct(
                data_path, grid_scan_params, grid_scan_params.z_steps
            )
            assert isinstance(sam_z := data_path["sam_z"], h5py.Dataset)
            assert_varying_axis_stride_correct(
                sam_z[:], grid_scan_params, grid_scan_params.z_axis
            )
            assert_axis_data_fixed(written_nexus_file, "y", grid_scan_params.y2_start)
            assert isinstance(
                flux := written_nexus_file["/entry/instrument/beam/total_flux"],
                h5py.Dataset,
            )
            assert flux[()] == TEST_FLUX
            assert_contains_external_link(data_path, "data_000001", "dummy_1_000001.h5")
            assert_contains_external_link(data_path, "data_000002", "dummy_1_000002.h5")
            assert isinstance(omega := data_path["omega"], h5py.Dataset)
            assert np.all(omega[:] == 90.0)
            assert np.all(
                written_nexus_file["/entry/data/sam_z"].attrs.get("vector")
                == [
                    0.0,
                    0.0,
                    1.0,
                ]
            )

    assert_data_edge_at(nexus_writer_2.nexus_file, 419)


def assert_x_data_stride_correct(data_path, grid_scan_params, varying_axis_steps):
    sam_x_data = data_path["sam_x"][:]
    assert len(sam_x_data) == (grid_scan_params.x_steps) * (varying_axis_steps)
    assert sam_x_data[1] - sam_x_data[0] == pytest.approx(grid_scan_params.x_step_size)


def assert_varying_axis_stride_correct(
    axis_data, grid_scan_params: GridScanParams, varying_axis: GridAxis
):
    assert len(axis_data) == (grid_scan_params.x_steps) * (varying_axis.full_steps)
    assert axis_data[grid_scan_params.x_steps + 1] - axis_data[0] == pytest.approx(
        varying_axis.step_size
    )


def assert_axis_data_fixed(written_nexus_file, axis, expected_value):
    if f"sam_{axis}" in written_nexus_file["/entry/data"]:
        fixed_data = written_nexus_file["/entry/data"][f"sam_{axis}"][:]
        assert sum(fixed_data) == len(fixed_data) * fixed_data[0]


def assert_data_edge_at(nexus_file, expected_edge_index):
    """Asserts that the datafile's last datapoint is at the specified index"""
    with h5py.File(nexus_file) as f:
        assert isinstance(data := f["entry/data/data"], h5py.Dataset)
        assert data[expected_edge_index, 0, 0] == 0
        with pytest.raises(IndexError):
            assert data[expected_edge_index + 1, 0, 0] == 0


def assert_contains_external_link(data_path, entry_name, file_name):
    assert entry_name in data_path
    assert data_path[entry_name].file.filename.endswith(file_name)


def test_nexus_writer_files_are_formatted_as_expected(
    test_fgs_params: ThreeDGridScan, single_dummy_file: NexusWriter
):
    for file in [single_dummy_file.nexus_file, single_dummy_file.master_file]:
        file_name = os.path.basename(file.name)
        expected_file_name_prefix = test_fgs_params.file_name + "_1"
        assert file_name.startswith(expected_file_name_prefix)


def test_nexus_writer_writes_width_and_height_correctly(single_dummy_file: NexusWriter):
    assert len(single_dummy_file.detector.detector_params.image_size) >= 2
    assert (
        single_dummy_file.detector.detector_params.image_size[0] == PIXELS_Y_EIGER2_X_4M
    )
    assert (
        single_dummy_file.detector.detector_params.image_size[1] == PIXELS_X_EIGER2_X_4M
    )


@patch.dict(os.environ, {"BEAMLINE": "I03"})
def test_nexus_writer_writes_beamline_name_correctly(
    test_fgs_params: ThreeDGridScan,
):
    d_size = test_fgs_params.detector_params.detector_size_constants.det_size_pixels
    data_shape = (test_fgs_params.num_images, d_size.width, d_size.height)
    nexus_writer = NexusWriter(test_fgs_params, data_shape, test_fgs_params.scan_points)
    assert nexus_writer.source.beamline == "I03"


def check_validity_through_zocalo(nexus_writers: tuple[NexusWriter, NexusWriter]):
    import dlstbx.swmr.h5check

    nexus_writer_1, nexus_writer_2 = nexus_writers

    nexus_writer_1.create_nexus_file(np.uint16)
    nexus_writer_2.create_nexus_file(np.uint16)

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


@pytest.mark.dlstbx
def test_nexus_file_validity_for_zocalo_with_two_linked_datasets(
    dummy_nexus_writers: tuple[NexusWriter, NexusWriter],
):
    check_validity_through_zocalo(dummy_nexus_writers)


@pytest.mark.dlstbx
def test_nexus_file_validity_for_zocalo_with_three_linked_datasets(
    dummy_nexus_writers_with_more_images: tuple[NexusWriter, NexusWriter],
):
    check_validity_through_zocalo(dummy_nexus_writers_with_more_images)


@pytest.mark.skip("Requires #87 of nexgen")
def test_given_some_datafiles_outside_of_VDS_range_THEN_they_are_not_in_nexus_file(
    dummy_nexus_writers_with_more_images: tuple[NexusWriter, NexusWriter],
):
    nexus_writer_1, nexus_writer_2 = dummy_nexus_writers_with_more_images

    nexus_writer_1.create_nexus_file(np.uint16)
    nexus_writer_2.create_nexus_file(np.uint16)

    for filename in [nexus_writer_1.nexus_file, nexus_writer_1.master_file]:
        with h5py.File(filename, "r") as written_nexus_file:
            assert isinstance(data := written_nexus_file["entry/data"], h5py.Dataset)
            assert "data_000001" in data
            assert "data_000002" in data
            assert "data_000003" not in data

    for filename in [nexus_writer_2.nexus_file, nexus_writer_2.master_file]:
        with h5py.File(filename, "r") as written_nexus_file:
            assert isinstance(data := written_nexus_file["entry/data"], h5py.Dataset)
            assert "data_000001" not in data
            assert "data_000002" in data
            assert "data_000003" in data


def test_given_data_files_not_yet_written_when_nexus_files_created_then_nexus_files_still_written(
    test_fgs_params: ThreeDGridScan,
):
    test_fgs_params.file_name = "non_existant_file"
    with create_nexus_writers(test_fgs_params) as (
        nexus_writer_1,
        nexus_writer_2,
    ):
        nexus_writer_1.create_nexus_file(np.uint16)
        nexus_writer_2.create_nexus_file(np.uint16)

        for filename in [
            nexus_writer_1.nexus_file,
            nexus_writer_1.master_file,
            nexus_writer_1.nexus_file,
            nexus_writer_1.master_file,
        ]:
            assert os.path.exists(filename)
