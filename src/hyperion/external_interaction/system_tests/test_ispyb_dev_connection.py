import pytest

from hyperion.external_interaction.ispyb.store_in_ispyb import (
    Store2DGridscanInIspyb,
    Store3DGridscanInIspyb,
    StoreGridscanInIspyb,
)
from hyperion.parameters.constants import DEV_ISPYB_DATABASE_CFG
from hyperion.parameters.external_parameters import from_file as default_raw_params
from hyperion.parameters.plan_specific.fgs_internal_params import (
    GridscanInternalParameters,
)


@pytest.mark.s03
def test_ispyb_get_comment_from_collection_correctly(fetch_comment):
    expected_comment_contents = (
        "Xray centring - "
        "Diffraction grid scan of 1 by 41 images, "
        "Top left [454,-4], Bottom right [455,772]"
    )

    assert fetch_comment(8292317) == expected_comment_contents

    assert fetch_comment(2) == ""


@pytest.mark.s03
def test_ispyb_deposition_comment_correct_on_failure(
    dummy_ispyb: Store2DGridscanInIspyb, fetch_comment
):
    dcid = dummy_ispyb.begin_deposition()
    dummy_ispyb.end_deposition("fail", "could not connect to devices")
    assert (
        fetch_comment(dcid[0][0])
        == "Hyperion: Xray centring - Diffraction grid scan of 40 by 20 images in 100.0 um by 100.0 um steps. Top left (px): [100,100], bottom right (px): [3300,1700]. DataCollection Unsuccessful reason: could not connect to devices"
    )


@pytest.mark.s03
def test_ispyb_deposition_comment_correct_for_3D_on_failure(
    dummy_ispyb_3d: Store3DGridscanInIspyb, fetch_comment
):
    dcid = dummy_ispyb_3d.begin_deposition()
    dcid1 = dcid[0][0]
    dcid2 = dcid[0][1]
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
    StoreClass, exp_num_of_grids, success, fetch_comment
):
    test_params = GridscanInternalParameters(**default_raw_params())
    test_params.hyperion_params.ispyb_params.visit_path = "/tmp/cm31105-4/"
    ispyb: StoreGridscanInIspyb = StoreClass(DEV_ISPYB_DATABASE_CFG, test_params)
    dc_ids, grid_ids, dcg_id = ispyb.begin_deposition()

    assert len(dc_ids) == exp_num_of_grids
    assert len(grid_ids) == exp_num_of_grids
    assert isinstance(dcg_id, int)

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

    if not success:
        ispyb.end_deposition("fail", "In error")
        expected_comments = [
            e + " DataCollection Unsuccessful reason: In error"
            for e in expected_comments
        ]
    else:
        ispyb.end_deposition("success", "")

    for grid_no, dc_id in enumerate(dc_ids):
        assert fetch_comment(dc_id) == expected_comments[grid_no]
