from __future__ import annotations

import os
from typing import Any, Callable, Literal
from unittest.mock import patch

import pytest
from bluesky.run_engine import RunEngine
from dodal.devices.attenuator import Attenuator
from dodal.devices.flux import Flux
from dodal.devices.s4_slit_gaps import S4SlitGaps
from dodal.devices.synchrotron import Synchrotron
from dodal.devices.undulator import Undulator

from hyperion.experiment_plans.rotation_scan_plan import (
    RotationScanComposite,
    rotation_scan,
)
from hyperion.external_interaction.callbacks.rotation.callback_collection import (
    RotationCallbackCollection,
)
from hyperion.external_interaction.ispyb.gridscan_ispyb_store import (
    StoreGridscanInIspyb,
)
from hyperion.external_interaction.ispyb.gridscan_ispyb_store_2d import (
    Store2DGridscanInIspyb,
)
from hyperion.external_interaction.ispyb.gridscan_ispyb_store_3d import (
    Store3DGridscanInIspyb,
)
from hyperion.external_interaction.ispyb.ispyb_store import (
    IspybIds,
)
from hyperion.parameters.constants import DEV_ISPYB_DATABASE_CFG
from hyperion.parameters.external_parameters import from_file as default_raw_params
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)
from hyperion.utils.utils import convert_angstrom_to_eV

from ...conftest import fake_read


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
    dummy_ispyb: Store2DGridscanInIspyb, fetch_comment: Callable[..., Any]
):
    dcid = dummy_ispyb.begin_deposition()
    dummy_ispyb.end_deposition("fail", "could not connect to devices")
    assert (
        fetch_comment(dcid.data_collection_ids[0])  # type: ignore
        == "Hyperion: Xray centring - Diffraction grid scan of 40 by 20 images in 100.0 um by 100.0 um steps. Top left (px): [100,100], bottom right (px): [3300,1700]. DataCollection Unsuccessful reason: could not connect to devices"
    )


@pytest.mark.s03
def test_ispyb_deposition_comment_correct_for_3D_on_failure(
    dummy_ispyb_3d: Store3DGridscanInIspyb, fetch_comment: Callable[..., Any]
):
    dcid = dummy_ispyb_3d.begin_deposition()
    dcid1 = dcid.data_collection_ids[0]  # type: ignore
    dcid2 = dcid.data_collection_ids[1]  # type: ignore
    dummy_ispyb_3d.end_deposition("fail", "could not connect to devices")
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
    "StoreClass, exp_num_of_grids, success",
    [
        (Store2DGridscanInIspyb, 1, False),
        (Store2DGridscanInIspyb, 1, True),
        (Store3DGridscanInIspyb, 2, False),
        (Store3DGridscanInIspyb, 2, True),
    ],
)
def test_can_store_2D_ispyb_data_correctly_when_in_error(
    StoreClass: type[Store2DGridscanInIspyb] | type[Store3DGridscanInIspyb],
    exp_num_of_grids: Literal[1, 2],
    success: bool,
    fetch_comment: Callable[..., Any],
):
    test_params = GridscanInternalParameters(**default_raw_params())
    test_params.hyperion_params.ispyb_params.visit_path = "/tmp/cm31105-4/"
    ispyb: StoreGridscanInIspyb = StoreClass(DEV_ISPYB_DATABASE_CFG, test_params)
    ispyb_ids: IspybIds = ispyb.begin_deposition()

    assert len(ispyb_ids.data_collection_ids) == exp_num_of_grids  # type: ignore
    assert len(ispyb_ids.grid_ids) == exp_num_of_grids  # type: ignore
    assert isinstance(ispyb_ids.data_collection_group_id, int)

    expected_comments = [
        (
            "Hyperion: Xray centring - Diffraction grid scan of 40 by 20 "
            "images in 100.0 um by 100.0 um steps. Top left (px): [0,0], bottom right (px): [0,0]."
        ),
        (
            "Hyperion: Xray centring - Diffraction grid scan of 40 by 10 "
            "images in 100.0 um by 100.0 um steps. Top left (px): [0,0], bottom right (px): [0,0]."
        ),
    ]

    if success:
        ispyb.end_deposition("success", "")
    else:
        ispyb.end_deposition("fail", "In error")
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


@pytest.mark.s03
@patch("bluesky.plan_stubs.wait")
@patch("hyperion.external_interaction.callbacks.rotation.nexus_callback.NexusWriter")
@patch(
    "hyperion.external_interaction.callbacks.rotation.callback_collection.RotationZocaloCallback"
)
def test_ispyb_deposition_in_rotation_plan(
    bps_wait,
    nexus_writer,
    zocalo_callback,
    fake_create_rotation_devices: RotationScanComposite,
    RE: RunEngine,
    test_rotation_params: RotationInternalParameters,
    fetch_comment: Callable[..., Any],
    fetch_datacollection_attribute: Callable[..., Any],
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

    test_rotation_params.experiment_params.image_width = test_img_wid
    test_rotation_params.hyperion_params.ispyb_params.beam_size_x = test_bs_x
    test_rotation_params.hyperion_params.ispyb_params.beam_size_y = test_bs_y
    test_rotation_params.hyperion_params.detector_params.exposure_time = test_exp_time
    test_rotation_params.hyperion_params.ispyb_params.current_energy_ev = (
        convert_angstrom_to_eV(test_wl)
    )
    test_rotation_params.hyperion_params.detector_params.expected_energy_ev = (
        convert_angstrom_to_eV(test_wl)
    )

    os.environ["ISPYB_CONFIG_PATH"] = DEV_ISPYB_DATABASE_CFG
    callbacks = RotationCallbackCollection.setup()
    for cb in list(callbacks):
        RE.subscribe(cb)

    composite = RotationScanComposite(
        attenuator=attenuator,
        backlight=fake_create_devices["backlight"],
        dcm=fake_create_devices["dcm"],
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

    dcid = callbacks.ispyb_handler.ispyb_ids.data_collection_ids
    assert dcid is not None
    comment = fetch_comment(dcid)
    assert comment == "Hyperion rotation scan"
    wavelength = fetch_datacollection_attribute(dcid, "wavelength")
    beamsize_x = fetch_datacollection_attribute(dcid, "beamSizeAtSampleX")
    beamsize_y = fetch_datacollection_attribute(dcid, "beamSizeAtSampleY")
    exposure = fetch_datacollection_attribute(dcid, "exposureTime")

    assert wavelength == test_wl
    assert beamsize_x == test_bs_x
    assert beamsize_y == test_bs_y
    assert exposure == test_exp_time
