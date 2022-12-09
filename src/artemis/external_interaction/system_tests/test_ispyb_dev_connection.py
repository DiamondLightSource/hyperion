import pytest

from artemis.external_interaction.ispyb.store_in_ispyb import (
    StoreInIspyb,
    StoreInIspyb2D,
    StoreInIspyb3D,
)
from artemis.parameters.internal_parameters import InternalParameters

ISPYB_CONFIG = "/dls_sw/dasc/mariadb/credentials/ispyb-dev.cfg"


@pytest.mark.s03
def test_ispyb_get_comment_from_collection_correctly():
    test_params = InternalParameters()
    ispyb = StoreInIspyb2D(ISPYB_CONFIG, test_params)

    expected_comment_contents = (
        "Xray centring - "
        "Diffraction grid scan of 1 by 41 images, "
        "Top left [454,-4], Bottom right [455,772]"
    )

    assert (
        ispyb.get_current_datacollection_comment(8292317) == expected_comment_contents
    )

    assert ispyb.get_current_datacollection_comment(2) == ""


@pytest.mark.s03
@pytest.mark.parametrize(
    "StoreClass, exp_num_of_grids, success",
    [
        (StoreInIspyb2D, 1, False),
        (StoreInIspyb2D, 1, True),
        (StoreInIspyb3D, 2, False),
        (StoreInIspyb3D, 2, True),
    ],
)
def test_can_store_2D_ispyb_data_correctly_when_in_error(
    StoreClass, exp_num_of_grids, success
):
    test_params = InternalParameters()
    test_params.artemis_params.ispyb_params.visit_path = "/tmp/cm31105-4/"
    ispyb: StoreInIspyb = StoreClass(ISPYB_CONFIG, test_params)
    dc_ids, grid_ids, dcg_id = ispyb.begin_deposition()

    assert len(dc_ids) == exp_num_of_grids
    assert len(grid_ids) == exp_num_of_grids
    assert isinstance(dcg_id, int)

    expected_comments = [
        (
            "Artemis: Xray centring - Diffraction grid scan of 4 by 200 "
            "images in 0.1 mm by 0.1 mm steps. Top left (px): [0,0], bottom right (px): [0,0]."
        ),
        (
            "Artemis: Xray centring - Diffraction grid scan of 4 by 61 "
            "images in 0.1 mm by 0.1 mm steps. Top left (px): [0,0], bottom right (px): [0,0]."
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
        assert (
            ispyb.get_current_datacollection_comment(dc_id)
            == expected_comments[grid_no]
        )
