import uuid
from typing import Callable
from unittest.mock import MagicMock, patch

import bluesky.preprocessors as bpp
import pytest
from bluesky.run_engine import RunEngine
from dodal.devices.aperturescatterguard import AperturePositions

import artemis.experiment_plans.fast_grid_scan_plan as fgs_plan
from artemis.exceptions import WarningException
from artemis.experiment_plans.fast_grid_scan_plan import (
    FGSComposite,
    fast_grid_scan,
    read_hardware_for_ispyb,
    run_gridscan,
)
from artemis.external_interaction.callbacks.fgs.fgs_callback_collection import (
    FGSCallbackCollection,
)
from artemis.external_interaction.system_tests.conftest import (  # noqa
    fetch_comment,
    zocalo_env,
)
from artemis.external_interaction.system_tests.test_ispyb_dev_connection import (
    ISPYB_CONFIG,
)
from artemis.parameters.beamline_parameters import GDABeamlineParameters
from artemis.parameters.constants import BEAMLINE_PARAMETER_PATHS, SIM_BEAMLINE
from artemis.parameters.external_parameters import from_file as default_raw_params
from artemis.parameters.plan_specific.fgs_internal_params import FGSInternalParameters


@pytest.fixture
def params():
    params = FGSInternalParameters(**default_raw_params())
    params.artemis_params.beamline = SIM_BEAMLINE
    return params


@pytest.fixture
def RE():
    return RunEngine({})


@pytest.fixture
def fgs_composite():
    fast_grid_scan_composite = FGSComposite()
    fgs_plan.fast_grid_scan_composite = fast_grid_scan_composite
    gda_beamline_parameters = GDABeamlineParameters.from_file(
        BEAMLINE_PARAMETER_PATHS["i03"]
    )
    aperture_positions = AperturePositions.from_gda_beamline_params(
        gda_beamline_parameters
    )
    fast_grid_scan_composite.aperture_scatterguard.load_aperture_positions(
        aperture_positions
    )
    fast_grid_scan_composite.aperture_scatterguard.aperture.z.move(
        aperture_positions.LARGE[2], wait=True
    )
    fast_grid_scan_composite.eiger.cam.manual_trigger.put("Yes")

    # S03 currently does not have StaleParameters_RBV
    fast_grid_scan_composite.eiger.wait_for_stale_parameters = lambda: None
    fast_grid_scan_composite.eiger.odin.check_odin_initialised = lambda: (True, "")

    fast_grid_scan_composite.aperture_scatterguard.scatterguard.x.set_lim(-4.8, 5.7)
    return fast_grid_scan_composite


@pytest.mark.skip(reason="Broken due to eiger issues in s03")
@pytest.mark.s03
@patch("bluesky.plan_stubs.wait", autospec=True)
@patch("bluesky.plan_stubs.kickoff", autospec=True)
@patch("bluesky.plan_stubs.complete", autospec=True)
@patch("artemis.fast_grid_scan_plan.wait_for_fgs_valid", autospec=True)
def test_run_gridscan(
    wait_for_fgs_valid: MagicMock,
    complete: MagicMock,
    kickoff: MagicMock,
    wait: MagicMock,
    params: FGSInternalParameters,
    RE: RunEngine,
    fgs_composite: FGSComposite,
):
    fgs_composite.eiger.unstage = lambda: True
    # Would be better to use fast_grid_scan instead but eiger doesn't work well in S03
    RE(run_gridscan(fgs_composite, params))


@pytest.mark.s03
def test_read_hardware_for_ispyb(
    RE: RunEngine,
    fgs_composite: FGSComposite,
):
    undulator = fgs_composite.undulator
    synchrotron = fgs_composite.synchrotron
    slit_gaps = fgs_composite.s4_slit_gaps

    @bpp.run_decorator()
    def read_run(u, s, g):
        yield from read_hardware_for_ispyb(u, s, g)

    RE(read_run(undulator, synchrotron, slit_gaps))


@pytest.mark.s03
@patch(
    "artemis.experiment_plans.fast_grid_scan_plan.fast_grid_scan_composite",
    autospec=True,
)
@patch("bluesky.plan_stubs.wait", autospec=True)
@patch("bluesky.plan_stubs.kickoff", autospec=True)
@patch("bluesky.plan_stubs.complete", autospec=True)
@patch(
    "artemis.experiment_plans.fast_grid_scan_plan.run_gridscan_and_move", autospec=True
)
@patch(
    "artemis.experiment_plans.fast_grid_scan_plan.set_zebra_shutter_to_manual",
    autospec=True,
)
def test_full_plan_tidies_at_end(
    set_shutter_to_manual: MagicMock,
    run_gridscan_and_move: MagicMock,
    complete: MagicMock,
    kickoff: MagicMock,
    wait: MagicMock,
    fgs_composite: FGSComposite,
    params: FGSInternalParameters,
    RE: RunEngine,
):
    callbacks = FGSCallbackCollection.from_params(params)
    callbacks.nexus_handler.nexus_writer_1 = MagicMock()
    callbacks.nexus_handler.nexus_writer_2 = MagicMock()
    callbacks.ispyb_handler.ispyb_ids = MagicMock()
    callbacks.ispyb_handler.ispyb.datacollection_ids = MagicMock()
    RE(fast_grid_scan(params, callbacks))
    set_shutter_to_manual.assert_called_once()


@pytest.mark.s03
@patch(
    "artemis.experiment_plans.fast_grid_scan_plan.fast_grid_scan_composite",
    autospec=True,
)
@patch("bluesky.plan_stubs.wait", autospec=True)
@patch("bluesky.plan_stubs.kickoff", autospec=True)
@patch("bluesky.plan_stubs.complete", autospec=True)
@patch(
    "artemis.experiment_plans.fast_grid_scan_plan.run_gridscan_and_move", autospec=True
)
@patch(
    "artemis.experiment_plans.fast_grid_scan_plan.set_zebra_shutter_to_manual",
    autospec=True,
)
def test_full_plan_tidies_at_end_when_plan_fails(
    set_shutter_to_manual: MagicMock,
    run_gridscan_and_move: MagicMock,
    complete: MagicMock,
    kickoff: MagicMock,
    wait: MagicMock,
    fgs_composite: FGSComposite,
    params: FGSInternalParameters,
    RE: RunEngine,
):
    callbacks = FGSCallbackCollection.from_params(params)
    run_gridscan_and_move.side_effect = Exception()
    with pytest.raises(Exception):
        RE(fast_grid_scan(params, callbacks))
    set_shutter_to_manual.assert_called_once()


@pytest.mark.s03
def test_GIVEN_scan_invalid_WHEN_plan_run_THEN_ispyb_entry_made_but_no_zocalo_entry(
    RE: RunEngine,
    fgs_composite: FGSComposite,
    fetch_comment: Callable,
    params: FGSInternalParameters,
):
    params.artemis_params.detector_params.directory = "./tmp"
    params.artemis_params.detector_params.prefix = str(uuid.uuid1())
    params.artemis_params.ispyb_params.visit_path = "/dls/i03/data/2022/cm31105-5/"

    # Currently s03 calls anything with z_steps > 1 invalid
    params.experiment_params.z_steps = 100

    callbacks = FGSCallbackCollection.from_params(params)
    callbacks.ispyb_handler.ispyb.ISPYB_CONFIG_PATH = ISPYB_CONFIG
    mock_start_zocalo = MagicMock()
    callbacks.zocalo_handler.zocalo_interactor.run_start = mock_start_zocalo

    with pytest.raises(WarningException):
        RE(fast_grid_scan(params, callbacks))

    dcid_used = callbacks.ispyb_handler.ispyb.datacollection_ids[0]

    comment = fetch_comment(dcid_used)

    assert "too long/short/bent" in comment
    mock_start_zocalo.assert_not_called()


@pytest.mark.s03
@patch("artemis.experiment_plans.fast_grid_scan_plan.bps.kickoff", autospec=True)
@patch("artemis.experiment_plans.fast_grid_scan_plan.bps.complete", autospec=True)
def test_WHEN_plan_run_THEN_move_to_centre_returned_from_zocalo_expected_centre(
    complete: MagicMock,
    kickoff: MagicMock,
    RE: RunEngine,
    fgs_composite: FGSComposite,
    zocalo_env: None,
    params: FGSInternalParameters,
):
    """This test currently avoids hardware interaction and is mostly confirming
    interaction with dev_ispyb and dev_zocalo"""

    params.artemis_params.detector_params.directory = "./tmp"
    params.artemis_params.detector_params.prefix = str(uuid.uuid1())
    params.artemis_params.ispyb_params.visit_path = "/dls/i03/data/2022/cm31105-5/"

    # Currently s03 calls anything with z_steps > 1 invalid
    params.experiment_params.z_steps = 1

    fgs_composite.eiger.stage = MagicMock()
    fgs_composite.eiger.unstage = MagicMock()

    callbacks = FGSCallbackCollection.from_params(params)
    callbacks.ispyb_handler.ispyb.ISPYB_CONFIG_PATH = ISPYB_CONFIG

    RE(fast_grid_scan(params, callbacks))

    # The following numbers are derived from the centre returned in fake_zocalo
    assert fgs_composite.sample_motors.x.user_readback.get() == pytest.approx(-0.05)
    assert fgs_composite.sample_motors.y.user_readback.get() == pytest.approx(0.05)
    assert fgs_composite.sample_motors.z.user_readback.get() == pytest.approx(0.15)
