import pytest

from artemis.external_interaction.ispyb.store_in_ispyb import StoreInIspyb2D
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
