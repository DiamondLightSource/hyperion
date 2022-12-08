import pytest

from artemis.external_interaction.callbacks.fgs.fgs_callback_collection import (
    FGSCallbackCollection,
)
from artemis.external_interaction.callbacks.fgs.zocalo_callback import (
    FGSZocaloCallback,
)
from artemis.parameters import FullParameters, Point3D


@pytest.mark.skip(reason="needs fake zocalo")
@pytest.mark.s03
def test_when_running_start_stop_then_get_expected_returned_results():
    params = FullParameters()
    zc: FGSZocaloCallback = FGSCallbackCollection.from_params(params).zocalo_handler
    dcids = [1, 2]
    for dcid in dcids:
        zc._run_start(dcid)
    for dcid in dcids:
        zc._run_end(dcid)
    assert zc._wait_for_result(4) == Point3D(x=3.4, y=2.3, z=1.2)
