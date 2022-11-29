import pytest

from artemis.external_interaction.fgs_callback_collection import FGSCallbackCollection
from artemis.parameters import FullParameters, Point3D


@pytest.mark.s03
def test_when_running_start_stop_then_get_expected_returned_results():

    params = FullParameters(zocalo_environment="devrmq")

    zocalo = FGSCallbackCollection.from_params(params).zocalo_handler

    dcids = [1, 2]
    for dcid in dcids:
        zocalo._run_start(dcid)
    for dcid in dcids:
        zocalo._run_end(dcid)
    assert zocalo._wait_for_result(4) == Point3D(x=3.4, y=2.3, z=1.2)
