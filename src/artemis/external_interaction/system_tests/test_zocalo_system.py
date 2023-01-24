from unittest.mock import MagicMock

import pytest

from artemis.external_interaction.callbacks.fgs.fgs_callback_collection import (
    FGSCallbackCollection,
)
from artemis.external_interaction.callbacks.fgs.zocalo_callback import FGSZocaloCallback
from artemis.parameters import FullParameters, Point3D


@pytest.mark.s03
def test_when_running_start_stop_then_get_expected_returned_results():
    params = FullParameters()
    zc: FGSZocaloCallback = FGSCallbackCollection.from_params(params).zocalo_handler
    dcids = [1, 2]
    for dcid in dcids:
        zc.zocalo_interactor.run_start(dcid)
    for dcid in dcids:
        zc.zocalo_interactor.run_end(dcid)
    assert zc.zocalo_interactor.wait_for_result(4) == Point3D(x=3.4, y=2.3, z=1.2)


@pytest.mark.s03
def test_zocalo_callback_calls_append_comment():
    params = FullParameters()
    zc: FGSZocaloCallback = FGSCallbackCollection.from_params(params).zocalo_handler
    zc.ispyb.append_to_comment = MagicMock()
    zc.ispyb.ispyb_ids = ([1, 2], 0, 4)
    dcids = [1, 2]
    for dcid in dcids:
        zc.zocalo_interactor.run_start(dcid)
    for dcid in dcids:
        zc.zocalo_interactor.run_end(dcid)
    zc.wait_for_results(fallback_xyz=Point3D(0, 0, 0))
    assert zc.ispyb.append_to_comment.call_count == 1
