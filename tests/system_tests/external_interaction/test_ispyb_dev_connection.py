from __future__ import annotations

import os
from copy import deepcopy
from typing import Any, Callable, Literal, Sequence
from unittest.mock import patch

import numpy
import pytest
from bluesky.run_engine import RunEngine
from dodal.devices.attenuator import Attenuator
from dodal.devices.flux import Flux
from dodal.devices.s4_slit_gaps import S4SlitGaps
from dodal.devices.synchrotron import Synchrotron, SynchrotronMode
from dodal.devices.undulator import Undulator

from hyperion.experiment_plans.rotation_scan_plan import (
    RotationScanComposite,
    rotation_scan,
)
from hyperion.external_interaction.callbacks.common.ispyb_mapping import (
    GridScanInfo,
    populate_data_collection_group,
    populate_data_collection_position_info,
    populate_remaining_data_collection_info,
)
from hyperion.external_interaction.callbacks.rotation.ispyb_callback import (
    RotationISPyBCallback,
)
from hyperion.external_interaction.callbacks.xray_centre.ispyb_mapping import (
    construct_comment_for_gridscan,
    populate_data_collection_grid_info,
    populate_xy_data_collection_info,
    populate_xz_data_collection_info,
)
from hyperion.external_interaction.ispyb.data_model import (
    ExperimentType,
    ScanDataInfo,
)
from hyperion.external_interaction.ispyb.ispyb_store import (
    IspybIds,
    StoreInIspyb,
)
from hyperion.parameters.constants import CONST
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)
from hyperion.utils.utils import convert_angstrom_to_eV

from ...conftest import fake_read


@pytest.fixture
def dummy_data_collection_group_info(dummy_params):
    return populate_data_collection_group(
        ExperimentType.GRIDSCAN_2D.value,
        dummy_params.hyperion_params.detector_params,
        dummy_params.hyperion_params.ispyb_params,
    )


@pytest.fixture
def dummy_scan_data_info_for_begin(dummy_params):
    info = populate_xy_data_collection_info(
        dummy_params.hyperion_params.detector_params,
    )
    info = populate_remaining_data_collection_info(
        None,
        None,
        info,
        dummy_params.hyperion_params.detector_params,
        dummy_params.hyperion_params.ispyb_params,
    )
    return ScanDataInfo(
        data_collection_info=info,
    )


def scan_xy_data_info_for_update(
    data_collection_group_id, dummy_params, scan_data_info_for_begin
):
    scan_data_info_for_update = deepcopy(scan_data_info_for_begin)
    grid_scan_info = GridScanInfo(
        numpy.array([100, 100, 50]),
        dummy_params.experiment_params.x_steps,
        dummy_params.experiment_params.y_steps,
        dummy_params.experiment_params.x_step_size,
        dummy_params.experiment_params.y_step_size,
    )
    scan_data_info_for_update.data_collection_info.comments = (
        construct_comment_for_gridscan(
            dummy_params.hyperion_params.ispyb_params, grid_scan_info
        )
    )
    scan_data_info_for_update.data_collection_info.parent_id = data_collection_group_id
    scan_data_info_for_update.data_collection_grid_info = (
        populate_data_collection_grid_info(
            dummy_params, grid_scan_info, dummy_params.hyperion_params.ispyb_params
        )
    )
    scan_data_info_for_update.data_collection_position_info = (
        populate_data_collection_position_info(
            dummy_params.hyperion_params.ispyb_params
        )
    )
    return scan_data_info_for_update


def scan_data_infos_for_update_3d(
    ispyb_ids, scan_xy_data_info_for_update, dummy_params
):
    upper_left = numpy.array([100, 100, 50])
    xz_grid_scan_info = GridScanInfo(
        [upper_left[0], upper_left[2]],
        dummy_params.experiment_params.x_steps,
        dummy_params.experiment_params.z_steps,
        dummy_params.experiment_params.x_step_size,
        dummy_params.experiment_params.z_step_size,
    )
    xz_data_collection_info = populate_xz_data_collection_info(
        dummy_params,
        dummy_params.hyperion_params.detector_params,
    )

    xz_data_collection_info = populate_remaining_data_collection_info(
        construct_comment_for_gridscan(
            dummy_params.hyperion_params.ispyb_params, xz_grid_scan_info
        ),
        ispyb_ids.data_collection_group_id,
        xz_data_collection_info,
        dummy_params.hyperion_params.detector_params,
        dummy_params.hyperion_params.ispyb_params,
    )
    xz_data_collection_info.parent_id = ispyb_ids.data_collection_group_id

    scan_xz_data_info_for_update = ScanDataInfo(
        data_collection_info=xz_data_collection_info,
        data_collection_grid_info=(
            populate_data_collection_grid_info(
                dummy_params,
                xz_grid_scan_info,
                dummy_params.hyperion_params.ispyb_params,
            )
        ),
        data_collection_position_info=(
            populate_data_collection_position_info(
                dummy_params.hyperion_params.ispyb_params
            )
        ),
    )
    return [scan_xy_data_info_for_update, scan_xz_data_info_for_update]


@pytest.mark.s03
def test_ispyb_get_comment_from_collection_correctly(fetch_comment: Callable[..., Any]):
    expected_comment_contents = (
        "Xray centring - "
        "Diffraction grid scan of 1 by 41 images, "
        "Top left [454,-4], Bottom right [455,772]"
    )

    assert fetch_comment(8292317) == expected_comment_contents

    assert fetch_comment(2) == ""


@pytest.mark.s03
def test_ispyb_deposition_comment_correct_on_failure(
    dummy_ispyb: StoreInIspyb,
    fetch_comment: Callable[..., Any],
    dummy_params,
    dummy_data_collection_group_info,
    dummy_scan_data_info_for_begin,
):
    ispyb_ids = dummy_ispyb.begin_deposition(
        dummy_data_collection_group_info, dummy_scan_data_info_for_begin
    )
    dummy_ispyb.end_deposition(ispyb_ids, "fail", "could not connect to devices")
    assert (
        fetch_comment(ispyb_ids.data_collection_ids[0])  # type: ignore
        == "DataCollection Unsuccessful reason: could not connect to devices"
    )


@pytest.mark.s03
def test_ispyb_deposition_comment_correct_for_3D_on_failure(
    dummy_ispyb_3d: StoreInIspyb,
    fetch_comment: Callable[..., Any],
    dummy_params,
    dummy_data_collection_group_info,
    dummy_scan_data_info_for_begin,
):
    ispyb_ids = dummy_ispyb_3d.begin_deposition(
        dummy_data_collection_group_info, dummy_scan_data_info_for_begin
    )
    scan_data_infos = generate_scan_data_infos(
        dummy_params,
        dummy_scan_data_info_for_begin,
        ExperimentType.GRIDSCAN_3D,
        ispyb_ids,
    )
    ispyb_ids = dummy_ispyb_3d.update_deposition(
        ispyb_ids, dummy_data_collection_group_info, scan_data_infos
    )
    dcid1 = ispyb_ids.data_collection_ids[0]  # type: ignore
    dcid2 = ispyb_ids.data_collection_ids[1]  # type: ignore
    dummy_ispyb_3d.end_deposition(ispyb_ids, "fail", "could not connect to devices")
    assert (
        fetch_comment(dcid1)
        == "Hyperion: Xray centring - Diffraction grid scan of 40 by 20 images in 100.0 um by 100.0 um steps. Top left (px): [100,100], bottom right (px): [3300,1700]. DataCollection Unsuccessful reason: could not connect to devices"
    )
    assert (
        fetch_comment(dcid2)
        == "Hyperion: Xray centring - Diffraction grid scan of 40 by 10 images in 100.0 um by 100.0 um steps. Top left (px): [100,50], bottom right (px): [3300,850]. DataCollection Unsuccessful reason: could not connect to devices"
    )


@pytest.mark.s03
@pytest.mark.parametrize(
    "experiment_type, exp_num_of_grids, success",
    [
        (ExperimentType.GRIDSCAN_2D, 1, False),
        (ExperimentType.GRIDSCAN_2D, 1, True),
        (ExperimentType.GRIDSCAN_3D, 2, False),
        (ExperimentType.GRIDSCAN_3D, 2, True),
    ],
)
def test_can_store_2D_ispyb_data_correctly_when_in_error(
    experiment_type,
    exp_num_of_grids: Literal[1, 2],
    success: bool,
    fetch_comment: Callable[..., Any],
    dummy_params,
    dummy_data_collection_group_info,
    dummy_scan_data_info_for_begin,
):
    ispyb: StoreInIspyb = StoreInIspyb(
        CONST.SIM.DEV_ISPYB_DATABASE_CFG, experiment_type
    )
    ispyb_ids: IspybIds = ispyb.begin_deposition(
        dummy_data_collection_group_info, dummy_scan_data_info_for_begin
    )
    scan_data_infos = generate_scan_data_infos(
        dummy_params, dummy_scan_data_info_for_begin, experiment_type, ispyb_ids
    )

    ispyb_ids = ispyb.update_deposition(
        ispyb_ids, dummy_data_collection_group_info, scan_data_infos
    )
    assert len(ispyb_ids.data_collection_ids) == exp_num_of_grids  # type: ignore
    assert len(ispyb_ids.grid_ids) == exp_num_of_grids  # type: ignore
    assert isinstance(ispyb_ids.data_collection_group_id, int)

    expected_comments = [
        (
            "Hyperion: Xray centring - Diffraction grid scan of 40 by 20 "
            "images in 100.0 um by 100.0 um steps. Top left (px): [100,100], bottom right (px): [3300,1700]."
        ),
        (
            "Hyperion: Xray centring - Diffraction grid scan of 40 by 10 "
            "images in 100.0 um by 100.0 um steps. Top left (px): [100,50], bottom right (px): [3300,850]."
        ),
    ]

    if success:
        ispyb.end_deposition(ispyb_ids, "success", "")
    else:
        ispyb.end_deposition(ispyb_ids, "fail", "In error")
        expected_comments = [
            e + " DataCollection Unsuccessful reason: In error"
            for e in expected_comments
        ]

    assert (
        not isinstance(ispyb_ids.data_collection_ids, int)
        and ispyb_ids.data_collection_ids is not None
    )
    for grid_no, dc_id in enumerate(ispyb_ids.data_collection_ids):
        assert fetch_comment(dc_id) == expected_comments[grid_no]


def generate_scan_data_infos(
    dummy_params,
    dummy_scan_data_info_for_begin: ScanDataInfo,
    experiment_type: ExperimentType,
    ispyb_ids: IspybIds,
) -> Sequence[ScanDataInfo]:
    xy_scan_data_info = scan_xy_data_info_for_update(
        ispyb_ids.data_collection_group_id, dummy_params, dummy_scan_data_info_for_begin
    )
    xy_scan_data_info.data_collection_id = ispyb_ids.data_collection_ids[0]
    if experiment_type == ExperimentType.GRIDSCAN_3D:
        scan_data_infos = scan_data_infos_for_update_3d(
            ispyb_ids, xy_scan_data_info, dummy_params
        )
    else:
        scan_data_infos = [xy_scan_data_info]
    return scan_data_infos


@pytest.mark.s03
@patch("bluesky.plan_stubs.wait")
def test_ispyb_deposition_in_rotation_plan(
    bps_wait,
    fake_create_rotation_devices: RotationScanComposite,
    RE: RunEngine,
    test_rotation_params: RotationInternalParameters,
    fetch_comment: Callable[..., Any],
    fetch_datacollection_attribute: Callable[..., Any],
    fetch_datacollectiongroup_attribute: Callable[..., Any],
    undulator: Undulator,
    attenuator: Attenuator,
    synchrotron: Synchrotron,
    s4_slit_gaps: S4SlitGaps,
    flux: Flux,
    robot,
    fake_create_devices: dict[str, Any],
):
    test_wl = 0.71
    test_bs_x = 0.023
    test_bs_y = 0.047
    test_exp_time = 0.023
    test_img_wid = 0.27
    test_undulator_current_gap = 1.12
    test_synchrotron_mode = SynchrotronMode.USER
    test_slit_gap_horiz = 0.123
    test_slit_gap_vert = 0.234

    test_rotation_params.experiment_params.image_width = test_img_wid
    test_rotation_params.hyperion_params.ispyb_params.beam_size_x = test_bs_x
    test_rotation_params.hyperion_params.ispyb_params.beam_size_y = test_bs_y
    test_rotation_params.hyperion_params.detector_params.exposure_time = test_exp_time
    energy_ev = convert_angstrom_to_eV(test_wl)
    fake_create_rotation_devices.dcm.energy_in_kev.user_readback.sim_put(  # pyright: ignore
        energy_ev / 1000
    )
    fake_create_rotation_devices.undulator.current_gap.sim_put(1.12)  # pyright: ignore
    fake_create_rotation_devices.synchrotron.machine_status.synchrotron_mode.sim_put(  # pyright: ignore
        test_synchrotron_mode.value
    )
    fake_create_rotation_devices.synchrotron.top_up.start_countdown.sim_put(  # pyright: ignore
        -1
    )
    fake_create_rotation_devices.s4_slit_gaps.xgap.user_readback.sim_put(  # pyright: ignore
        test_slit_gap_horiz
    )
    fake_create_rotation_devices.s4_slit_gaps.ygap.user_readback.sim_put(  # pyright: ignore
        test_slit_gap_vert
    )
    test_rotation_params.hyperion_params.detector_params.expected_energy_ev = energy_ev

    os.environ["ISPYB_CONFIG_PATH"] = CONST.SIM.DEV_ISPYB_DATABASE_CFG
    ispyb_cb = RotationISPyBCallback()
    RE.subscribe(ispyb_cb)

    composite = RotationScanComposite(
        attenuator=attenuator,
        backlight=fake_create_devices["backlight"],
        dcm=fake_create_rotation_devices.dcm,
        detector_motion=fake_create_devices["detector_motion"],
        eiger=fake_create_devices["eiger"],
        flux=flux,
        smargon=fake_create_devices["smargon"],
        undulator=undulator,
        synchrotron=synchrotron,
        s4_slit_gaps=s4_slit_gaps,
        zebra=fake_create_devices["zebra"],
        aperture_scatterguard=fake_create_devices["ap_sg"],
        robot=robot,
    )

    with patch("bluesky.preprocessors.__read_and_stash_a_motor", fake_read):
        RE(
            rotation_scan(
                composite,
                test_rotation_params,
            )
        )

    dcid = ispyb_cb.ispyb_ids.data_collection_ids[0]
    assert dcid is not None
    assert fetch_comment(dcid) == "Hyperion rotation scan"
    assert fetch_datacollection_attribute(dcid, "wavelength") == test_wl
    assert fetch_datacollection_attribute(dcid, "beamSizeAtSampleX") == test_bs_x
    assert fetch_datacollection_attribute(dcid, "beamSizeAtSampleY") == test_bs_y
    assert fetch_datacollection_attribute(dcid, "exposureTime") == test_exp_time
    assert (
        fetch_datacollection_attribute(dcid, "undulatorGap1")
        == test_undulator_current_gap
    )
    assert (
        fetch_datacollection_attribute(dcid, "synchrotronMode")
        == test_synchrotron_mode.value
    )
    assert (
        fetch_datacollection_attribute(dcid, "slitGapHorizontal") == test_slit_gap_horiz
    )
    assert fetch_datacollection_attribute(dcid, "slitGapVertical") == test_slit_gap_vert
    # TODO Can't test barcode as need BLSample which needs Dewar, Shipping, Container entries for the
    # upsert stored proc to use it.
