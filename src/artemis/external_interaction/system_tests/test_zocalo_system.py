import os

import pytest

from artemis.external_interaction.callbacks.fgs.fgs_callback_collection import (
    FGSCallbackCollection,
)
from artemis.external_interaction.callbacks.fgs.zocalo_callback import FGSZocaloCallback
from artemis.external_interaction.system_tests.conftest import TEST_RESULT_LARGE
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
    result = zc.zocalo_interactor.wait_for_result(4)
    assert result[0] == TEST_RESULT_LARGE[0]


@pytest.fixture
def run_zocalo_with_dev_ispyb(dummy_params, dummy_ispyb_3d):
    def inner(sample_name="", fallback=Point3D(0, 0, 0)):
        dummy_params.detector_params.prefix = sample_name
        zc: FGSZocaloCallback = FGSCallbackCollection.from_params(
            dummy_params
        ).zocalo_handler
        zc.ispyb.ispyb.ISPYB_CONFIG_PATH = dummy_ispyb_3d.ISPYB_CONFIG_PATH
        zc.ispyb.ispyb_ids = zc.ispyb.ispyb.begin_deposition()
        for dcid in zc.ispyb.ispyb_ids[0]:
            zc.zocalo_interactor.run_start(dcid)
        zc.stop({})
        centre, bbox = zc.wait_for_results(fallback_xyz=fallback)
        return zc, centre

    return inner


@pytest.mark.s03
def test_given_a_result_with_no_diffraction_when_zocalo_called_then_move_to_fallback(
    run_zocalo_with_dev_ispyb, zocalo_env
):
    fallback = Point3D(1, 2, 3)
    zc, centre = run_zocalo_with_dev_ispyb("NO_DIFF", fallback)
    assert centre == fallback


@pytest.mark.s03
def test_given_a_result_with_no_diffraction_ispyb_comment_updated(
    run_zocalo_with_dev_ispyb, zocalo_env, fetch_comment
):
    zc, centre = run_zocalo_with_dev_ispyb("NO_DIFF")

    comment = fetch_comment(zc.ispyb.ispyb_ids[0][0])
    assert "Found no diffraction." in comment


@pytest.mark.s03
def test_zocalo_adds_nonzero_comment_time(
    run_zocalo_with_dev_ispyb, zocalo_env, fetch_comment
):
    zc, centre = run_zocalo_with_dev_ispyb()

    comment = fetch_comment(zc.ispyb.ispyb_ids[0][0])
    assert comment[-29:-6] == "Zocalo processing took "
    assert float(comment[-6:-2]) > 0
    assert float(comment[-6:-2]) < 90


@pytest.mark.s03
def test_given_a_result_with_multiple_crystals_ispyb_comment_updated(
    run_zocalo_with_dev_ispyb, zocalo_env, fetch_comment
):
    zc, _ = run_zocalo_with_dev_ispyb("MULTI_X")

    comment = fetch_comment(zc.ispyb.ispyb_ids[0][0])
    assert "Found multiple crystals" in comment
