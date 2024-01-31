import uuid
from typing import Callable
from unittest.mock import MagicMock, patch

import bluesky.preprocessors as bpp
import pytest
from bluesky.run_engine import RunEngine
from dodal.beamlines import i03
from dodal.beamlines.beamline_parameters import (
    BEAMLINE_PARAMETER_PATHS,
    GDABeamlineParameters,
)
from dodal.devices.aperturescatterguard import AperturePositions
from ophyd.status import Status

from hyperion.device_setup_plans.read_hardware_for_setup import (
    read_hardware_for_ispyb_during_collection,
    read_hardware_for_ispyb_pre_collection,
)
from hyperion.exceptions import WarningException
from hyperion.experiment_plans.flyscan_xray_centre_plan import (
    FlyScanXRayCentreComposite,
    flyscan_xray_centre,
    run_gridscan,
    run_gridscan_and_move,
)
from hyperion.external_interaction.callbacks.xray_centre.callback_collection import (
    XrayCentreCallbackCollection,
)
from hyperion.external_interaction.ispyb.store_datacollection_in_ispyb import IspybIds
from hyperion.parameters.constants import DEV_ISPYB_DATABASE_CFG as ISPYB_CONFIG
from hyperion.parameters.constants import SIM_BEAMLINE
from hyperion.parameters.external_parameters import from_file as default_raw_params
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)

from ..external_interaction.conftest import (  # noqa
    fetch_comment,
    zocalo_env,
)


@pytest.fixture
def params():
    params = GridscanInternalParameters(**default_raw_params())
    params.hyperion_params.beamline = SIM_BEAMLINE
    return params


@pytest.fixture
def fgs_composite():
    composite = FlyScanXRayCentreComposite(
        attenuator=i03.attenuator(),
        aperture_scatterguard=i03.aperture_scatterguard(),
        backlight=i03.backlight(),
        eiger=i03.eiger(),
        fast_grid_scan=i03.fast_grid_scan(),
        flux=i03.flux(fake_with_ophyd_sim=True),
        s4_slit_gaps=i03.s4_slit_gaps(),
        smargon=i03.smargon(),
        undulator=i03.undulator(),
        synchrotron=i03.synchrotron(fake_with_ophyd_sim=True),
        xbpm_feedback=i03.xbpm_feedback(fake_with_ophyd_sim=True),
        zebra=i03.zebra(),
        zocalo=MagicMock(),
    )

    gda_beamline_parameters = GDABeamlineParameters.from_file(
        BEAMLINE_PARAMETER_PATHS["i03"]
    )

    aperture_positions = AperturePositions.from_gda_beamline_params(
        gda_beamline_parameters
    )
    composite.aperture_scatterguard.load_aperture_positions(aperture_positions)
    composite.aperture_scatterguard.aperture.z.move(
        aperture_positions.LARGE[2], wait=True
    )
    composite.eiger.cam.manual_trigger.put("Yes")
    composite.eiger.odin.check_odin_initialised = lambda: (True, "")
    composite.eiger.stage = MagicMock(return_value=Status(done=True, success=True))
    composite.eiger.unstage = MagicMock(return_value=Status(done=True, success=True))

    composite.aperture_scatterguard.scatterguard.x.set_lim(-4.8, 5.7)

    return composite


@pytest.mark.s03
@patch("bluesky.plan_stubs.wait", autospec=True)
@patch("bluesky.plan_stubs.kickoff", autospec=True)
@patch("bluesky.plan_stubs.complete", autospec=True)
@patch(
    "hyperion.experiment_plans.flyscan_xray_centre_plan.wait_for_gridscan_valid",
    autospec=True,
)
def test_run_gridscan(
    wait_for_gridscan_valid: MagicMock,
    complete: MagicMock,
    kickoff: MagicMock,
    wait: MagicMock,
    params: GridscanInternalParameters,
    RE: RunEngine,
    fgs_composite: FlyScanXRayCentreComposite,
):
    RE(run_gridscan(fgs_composite, params))


@pytest.mark.s03
@patch("bluesky.plan_stubs.wait", autospec=True)
@patch("bluesky.plan_stubs.kickoff", autospec=True)
@patch("bluesky.plan_stubs.complete", autospec=True)
@patch(
    "hyperion.experiment_plans.flyscan_xray_centre_plan.wait_for_gridscan_valid",
    autospec=True,
)
def test_run_gridscan_and_move(
    wait_for_gridscan_valid: MagicMock,
    complete: MagicMock,
    kickoff: MagicMock,
    wait: MagicMock,
    params: GridscanInternalParameters,
    RE: RunEngine,
    fgs_composite: FlyScanXRayCentreComposite,
):
    RE(run_gridscan_and_move(fgs_composite, params))


@pytest.mark.s03
def test_read_hardware_for_ispyb_pre_collection(
    RE: RunEngine,
    fgs_composite: FlyScanXRayCentreComposite,
):
    undulator = fgs_composite.undulator
    synchrotron = fgs_composite.synchrotron
    slit_gaps = fgs_composite.s4_slit_gaps
    attenuator = fgs_composite.attenuator
    flux = fgs_composite.flux
    dcm = fgs_composite.dcm
    aperture_scatterguard = fgs_composite.aperture_scatterguard

    @bpp.run_decorator()
    def read_run(u, s, g, a, f,dcm, ap_sg):
        yield from read_hardware_for_ispyb_pre_collection(u, s, g, ap_sg)
        yield from read_hardware_for_ispyb_during_collection(a, f, dcm)

    RE(read_run(undulator, synchrotron, slit_gaps, attenuator, flux, dcm, aperture_scatterguard))


@pytest.mark.s03
@patch("bluesky.plan_stubs.wait", autospec=True)
@patch("bluesky.plan_stubs.kickoff", autospec=True)
@patch("bluesky.plan_stubs.complete", autospec=True)
@patch(
    "hyperion.experiment_plans.flyscan_xray_centre_plan.run_gridscan_and_move",
    autospec=True,
)
@patch(
    "hyperion.experiment_plans.flyscan_xray_centre_plan.set_zebra_shutter_to_manual",
    autospec=True,
)
def test_full_plan_tidies_at_end(
    set_shutter_to_manual: MagicMock,
    run_gridscan_and_move: MagicMock,
    complete: MagicMock,
    kickoff: MagicMock,
    wait: MagicMock,
    fgs_composite: FlyScanXRayCentreComposite,
    params: GridscanInternalParameters,
    RE: RunEngine,
):
    callbacks = XrayCentreCallbackCollection.setup()
    callbacks.nexus_handler.nexus_writer_1 = MagicMock()
    callbacks.nexus_handler.nexus_writer_2 = MagicMock()
    callbacks.ispyb_handler.ispyb_ids = IspybIds(
        data_collection_ids=(0, 0), data_collection_group_id=0, grid_ids=(0,)
    )
    with patch(
        "hyperion.experiment_plans.flyscan_xray_centre_plan.XrayCentreCallbackCollection.setup",
        return_value=callbacks,
    ):
        RE(flyscan_xray_centre(fgs_composite, params))
    set_shutter_to_manual.assert_called_once()


@pytest.mark.s03
@patch("bluesky.plan_stubs.wait", autospec=True)
@patch("bluesky.plan_stubs.kickoff", autospec=True)
@patch("bluesky.plan_stubs.complete", autospec=True)
@patch(
    "hyperion.experiment_plans.flyscan_xray_centre_plan.run_gridscan_and_move",
    autospec=True,
)
@patch(
    "hyperion.experiment_plans.flyscan_xray_centre_plan.set_zebra_shutter_to_manual",
    autospec=True,
)
def test_full_plan_tidies_at_end_when_plan_fails(
    set_shutter_to_manual: MagicMock,
    run_gridscan_and_move: MagicMock,
    complete: MagicMock,
    kickoff: MagicMock,
    wait: MagicMock,
    fgs_composite: FlyScanXRayCentreComposite,
    params: GridscanInternalParameters,
    RE: RunEngine,
):
    run_gridscan_and_move.side_effect = Exception()
    with pytest.raises(Exception):
        RE(flyscan_xray_centre(fgs_composite, params))
    set_shutter_to_manual.assert_called_once()


@pytest.mark.s03
def test_GIVEN_scan_invalid_WHEN_plan_run_THEN_ispyb_entry_made_but_no_zocalo_entry(
    RE: RunEngine,
    fgs_composite: FlyScanXRayCentreComposite,
    fetch_comment: Callable,
    params: GridscanInternalParameters,
):
    params.hyperion_params.detector_params.directory = "./tmp"
    params.hyperion_params.detector_params.prefix = str(uuid.uuid1())
    params.hyperion_params.ispyb_params.visit_path = "/dls/i03/data/2022/cm31105-5/"

    # Currently s03 calls anything with z_steps > 1 invalid
    params.experiment_params.z_steps = 100

    callbacks = XrayCentreCallbackCollection.setup()
    callbacks.ispyb_handler.ispyb.ISPYB_CONFIG_PATH = ISPYB_CONFIG
    mock_start_zocalo = MagicMock()
    callbacks.zocalo_handler.zocalo_interactor.run_start = mock_start_zocalo

    with pytest.raises(WarningException):
        RE(flyscan_xray_centre(fgs_composite, params))

    dcid_used = callbacks.ispyb_handler.ispyb_ids = IspybIds(
        data_collection_ids=(0, 0), data_collection_group_id=0, grid_ids=(0,)
    )

    comment = fetch_comment(dcid_used)

    assert "too long/short/bent" in comment
    mock_start_zocalo.assert_not_called()


@pytest.mark.s03
@patch("hyperion.experiment_plans.flyscan_xray_centre_plan.bps.kickoff", autospec=True)
@patch("hyperion.experiment_plans.flyscan_xray_centre_plan.bps.complete", autospec=True)
def test_WHEN_plan_run_THEN_move_to_centre_returned_from_zocalo_expected_centre(
    complete: MagicMock,
    kickoff: MagicMock,
    RE: RunEngine,
    fgs_composite: FlyScanXRayCentreComposite,
    zocalo_env: None,
    params: GridscanInternalParameters,
):
    """This test currently avoids hardware interaction and is mostly confirming
    interaction with dev_ispyb and fake_zocalo"""

    params.hyperion_params.detector_params.directory = "./tmp"
    params.hyperion_params.detector_params.prefix = str(uuid.uuid1())
    params.hyperion_params.ispyb_params.visit_path = "/dls/i03/data/2022/cm31105-5/"

    # Currently s03 calls anything with z_steps > 1 invalid
    params.experiment_params.z_steps = 1

    fgs_composite.eiger.stage = MagicMock()
    fgs_composite.eiger.unstage = MagicMock()

    callbacks = XrayCentreCallbackCollection.setup()
    callbacks.ispyb_handler.ispyb.ISPYB_CONFIG_PATH = ISPYB_CONFIG

    RE(flyscan_xray_centre(fgs_composite, params))

    # The following numbers are derived from the centre returned in fake_zocalo
    assert fgs_composite.sample_motors.x.user_readback.get() == pytest.approx(-0.05)
    assert fgs_composite.sample_motors.y.user_readback.get() == pytest.approx(0.05)
    assert fgs_composite.sample_motors.z.user_readback.get() == pytest.approx(0.15)
