import pytest

from artemis.external_interaction.ispyb.store_in_ispyb import StoreInIspyb2D
from artemis.parameters import FullParameters

ISPYB_CONFIG = "/dls_sw/dasc/mariadb/credentials/ispyb-dev.cfg"


@pytest.mark.s03
def test_ispyb_get_comment_from_collection_correctly():
    test_params = FullParameters()
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
def test_can_store_2D_ispyb_data_correctly_when_in_error():
    test_params = FullParameters()
    test_params.ispyb_params.visit_path = "/tmp/cm31105-4/"
    ispyb = StoreInIspyb2D(ISPYB_CONFIG, test_params)
    dc_ids, grid_ids, dcg_id = ispyb.begin_deposition()

    assert len(dc_ids) == 1
    assert len(grid_ids) == 1
    assert isinstance(dcg_id, int)

    ispyb.end_deposition(False, "In error")
