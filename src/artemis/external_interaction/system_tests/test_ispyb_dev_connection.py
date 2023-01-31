from functools import partial
from typing import Callable

import ispyb.sqlalchemy
import pytest
from ispyb.sqlalchemy import DataCollection
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from artemis.external_interaction.ispyb.store_in_ispyb import (
    StoreInIspyb,
    StoreInIspyb2D,
    StoreInIspyb3D,
)
from artemis.parameters import FullParameters
from artemis.utils import Point3D

ISPYB_CONFIG = "/dls_sw/dasc/mariadb/credentials/ispyb-dev.cfg"


def get_current_datacollection_comment(Session: Callable, dcid: int) -> str:
    """Read the 'comments' field from the given datacollection id's ISPyB entry.
    Returns an empty string if the comment is not yet initialised.
    """
    try:
        with Session() as session:
            query = session.query(DataCollection).filter(
                DataCollection.dataCollectionId == dcid
            )
            current_comment: str = query.first().comments
    except Exception:
        current_comment = ""
    return current_comment


@pytest.fixture
def fetch_comment() -> Callable:
    url = ispyb.sqlalchemy.url(ISPYB_CONFIG)
    engine = create_engine(url, connect_args={"use_pure": True})
    Session = sessionmaker(engine)
    return partial(get_current_datacollection_comment, Session)


@pytest.fixture
def dummy_params():
    dummy_params = FullParameters()
    dummy_params.ispyb_params.upper_left = Point3D(100, 100, 50)
    dummy_params.ispyb_params.pixels_per_micron_x = 0.8
    dummy_params.ispyb_params.pixels_per_micron_y = 0.8
    dummy_params.ispyb_params.visit_path = "/dls/i03/data/2022/cm31105-5/"
    return dummy_params


@pytest.fixture
def dummy_ispyb(dummy_params):
    return StoreInIspyb2D(ISPYB_CONFIG, dummy_params)


@pytest.fixture
def dummy_ispyb_3d(dummy_params):
    return StoreInIspyb3D(ISPYB_CONFIG, dummy_params)


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
    dummy_ispyb: StoreInIspyb2D, fetch_comment
):
    dcid = dummy_ispyb.begin_deposition()
    dummy_ispyb.end_deposition("fail", "could not connect to devices")
    assert (
        fetch_comment(dcid[0][0])
        == "Artemis: Xray centring - Diffraction grid scan of 4 by 200 images in 100.0 um by 100.0 um steps. Top left (px): [100,100], bottom right (px): [420,16100]. DataCollection Unsuccessful reason: could not connect to devices"
    )


@pytest.mark.s03
def test_ispyb_deposition_comment_correct_for_3D_on_failure(
    dummy_ispyb_3d: StoreInIspyb3D, fetch_comment
):
    dcid = dummy_ispyb_3d.begin_deposition()
    dcid1 = dcid[0][0]
    dcid2 = dcid[0][1]
    dummy_ispyb_3d.end_deposition("fail", "could not connect to devices")
    assert (
        fetch_comment(dcid1)
        == "Artemis: Xray centring - Diffraction grid scan of 4 by 200 images in 100.0 um by 100.0 um steps. Top left (px): [100,100], bottom right (px): [420,16100]. DataCollection Unsuccessful reason: could not connect to devices"
    )
    assert (
        fetch_comment(dcid2)
        == "Artemis: Xray centring - Diffraction grid scan of 4 by 61 images in 100.0 um by 100.0 um steps. Top left (px): [100,50], bottom right (px): [420,4930]. DataCollection Unsuccessful reason: could not connect to devices"
    )


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
    StoreClass, exp_num_of_grids, success, fetch_comment
):
    test_params = FullParameters()
    test_params.ispyb_params.visit_path = "/tmp/cm31105-4/"
    ispyb: StoreInIspyb = StoreClass(ISPYB_CONFIG, test_params)
    dc_ids, grid_ids, dcg_id = ispyb.begin_deposition()

    assert len(dc_ids) == exp_num_of_grids
    assert len(grid_ids) == exp_num_of_grids
    assert isinstance(dcg_id, int)

    expected_comments = [
        (
            "Artemis: Xray centring - Diffraction grid scan of 4 by 200 "
            "images in 100.0 um by 100.0 um steps. Top left (px): [0,0], bottom right (px): [0,0]."
        ),
        (
            "Artemis: Xray centring - Diffraction grid scan of 4 by 61 "
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
