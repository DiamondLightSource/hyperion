import os
from unittest.mock import MagicMock

import pytest

from artemis.external_interaction.callbacks.fgs.fgs_callback_collection import (
    FGSCallbackCollection,
)
from artemis.external_interaction.callbacks.fgs.zocalo_callback import FGSZocaloCallback
from artemis.parameters import FullParameters, Point3D


@pytest.fixture
def zocalo_env():
    os.environ["ZOCALO_CONFIG"] = "/dls_sw/apps/zocalo/live/configuration.yaml"


@pytest.mark.s03
def test_when_running_start_stop_then_get_expected_returned_results(zocalo_env):
    params = FullParameters()
    zc: FGSZocaloCallback = FGSCallbackCollection.from_params(params).zocalo_handler
    dcids = [1, 2]
    zc.ispyb.ispyb_ids = (dcids, 0, 4)
    for dcid in dcids:
        zc.zocalo_interactor.run_start(dcid)
    for dcid in dcids:
        zc.zocalo_interactor.run_end(dcid)
    assert zc.zocalo_interactor.wait_for_result(4) == Point3D(x=1.2, y=2.3, z=1.4)


@pytest.mark.s03
def test_zocalo_callback_calls_append_comment(zocalo_env):
    params = FullParameters()
    zc: FGSZocaloCallback = FGSCallbackCollection.from_params(params).zocalo_handler
    zc.ispyb.append_to_comment = MagicMock()
    dcids = [1, 2]
    zc.ispyb.ispyb_ids = (dcids, 0, 4)
    for dcid in dcids:
        zc.zocalo_interactor.run_start(dcid)
    for dcid in dcids:
        zc.zocalo_interactor.run_end(dcid)
    zc.wait_for_results(fallback_xyz=Point3D(0, 0, 0))
    assert zc.ispyb.append_to_comment.call_count == 1


@pytest.mark.s03
def test_given_a_result_with_no_diffraction_when_zocalo_called_then_move_to_fallback(
    zocalo_env,
):
    params = FullParameters()
    NO_DIFFFRACTION_ID = 1
    zc: FGSZocaloCallback = FGSCallbackCollection.from_params(params).zocalo_handler
    zc.ispyb.append_to_comment = MagicMock()
    dcids = [NO_DIFFFRACTION_ID, NO_DIFFFRACTION_ID]
    zc.ispyb.ispyb_ids = (dcids, 0, NO_DIFFFRACTION_ID)
    for dcid in dcids:
        zc.zocalo_interactor.run_start(dcid)
    for dcid in dcids:
        zc.zocalo_interactor.run_end(dcid)
    fallback = Point3D(1, 2, 3)
    centre = zc.wait_for_results(fallback_xyz=fallback)
    assert centre == fallback


@pytest.mark.s03
def test_zocalo_adds_nonzero_comment_time(zocalo_env, dummy_ispyb_3d, fetch_comment):
    params = FullParameters()
    zc: FGSZocaloCallback = FGSCallbackCollection.from_params(params).zocalo_handler
    zc.ispyb.ispyb = dummy_ispyb_3d
    zc.ispyb.ispyb_ids = zc.ispyb.ispyb.begin_deposition()
    ispyb_numbers = zc.ispyb.ispyb_ids
    assert ispyb_numbers[0] is not None
    dcids = ispyb_numbers[0]
    for dcid in dcids:
        zc.zocalo_interactor.run_start(dcid)
    zc.stop({})
    zc.wait_for_results(fallback_xyz=Point3D(0, 0, 0))
    zc.ispyb.ispyb.end_deposition("success", "")

    comment = fetch_comment(ispyb_numbers[0][0])
    assert comment[-29:-6] == "Zocalo processing took "
    assert float(comment[-6:-2]) > 0
    assert float(comment[-6:-2]) < 90
