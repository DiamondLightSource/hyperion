import uuid
from typing import Callable
from unittest.mock import MagicMock, patch

import bluesky.plan_stubs as bps
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
from hyperion.device_setup_plans.xbpm_feedback import (
    transmission_and_xbpm_feedback_for_collection_decorator,
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
    yield params


@pytest.fixture
def RE():
    yield RunEngine({})


@pytest.fixture()
def callbacks(params):
    callbacks = XrayCentreCallbackCollection.setup()
    callbacks.ispyb_handler.ispyb.ISPYB_CONFIG_PATH = ISPYB_CONFIG
    yield callbacks


@pytest.fixture
def fxc_composite():
    composite = FlyScanXRayCentreComposite(
        attenuator=i03.attenuator(),
        aperture_scatterguard=i03.aperture_scatterguard(),
        backlight=i03.backlight(),
        dcm=i03.dcm(fake_with_ophyd_sim=True),
        eiger=i03.eiger(),
        fast_grid_scan=i03.fast_grid_scan(),
        flux=i03.flux(fake_with_ophyd_sim=True),
        panda=i03.panda(fake_with_ophyd_sim=True),
        panda_fast_grid_scan=i03.panda_fast_grid_scan(fake_with_ophyd_sim=True),
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

    composite.xbpm_feedback.pos_ok.sim_put(1)  # type: ignore
    composite.xbpm_feedback.pos_stable.sim_put(1)  # type: ignore

    return composite


@pytest.mark.s03
def test_s03_devices_connect(fxc_composite: FlyScanXRayCentreComposite):
    assert fxc_composite.aperture_scatterguard
    assert fxc_composite.backlight


@pytest.mark.skip(reason="Broken due to eiger issues in s03")
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
    fxc_composite: FlyScanXRayCentreComposite,
):
    # Would be better to use flyscan_xray_centre instead but eiger doesn't work well in S03
    RE(run_gridscan(fxc_composite, params))


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
    fxc_composite: FlyScanXRayCentreComposite,
):
    undulator = fxc_composite.undulator
    synchrotron = fxc_composite.synchrotron
    slit_gaps = fxc_composite.s4_slit_gaps
    attenuator = fxc_composite.attenuator
    flux = fxc_composite.flux
    dcm = fxc_composite.dcm

    @bpp.run_decorator()
    def read_run(u, s, g, a, f, dcm):
        yield from read_hardware_for_ispyb_pre_collection(u, s, g)
        yield from read_hardware_for_ispyb_during_collection(a, f, dcm)

    RE(read_run(undulator, synchrotron, slit_gaps, attenuator, flux, dcm))


@pytest.mark.s03
def test_xbpm_feedback_decorator(
    RE: RunEngine,
    fxc_composite: FlyScanXRayCentreComposite,
    params: GridscanInternalParameters,
    callbacks: XrayCentreCallbackCollection,
):
    # This test is currently kind of more a unit test since we are faking XBPM feedback
    # with ophyd.sim, but it should continue to pass when we replace it with something
    # in S03

    @transmission_and_xbpm_feedback_for_collection_decorator(
        fxc_composite.xbpm_feedback,
        fxc_composite.attenuator,
        params.hyperion_params.ispyb_params.transmission_fraction,
    )
    def decorated_plan():
        yield from bps.sleep(0.1)

    RE(decorated_plan())
    assert fxc_composite.xbpm_feedback.pos_stable.get() == 1


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
    fxc_composite: FlyScanXRayCentreComposite,
    params: GridscanInternalParameters,
    RE: RunEngine,
    callbacks: XrayCentreCallbackCollection,
):
    callbacks.nexus_handler.nexus_writer_1 = MagicMock()
    callbacks.nexus_handler.nexus_writer_2 = MagicMock()
    callbacks.ispyb_handler.ispyb_ids = IspybIds(
        data_collection_ids=(0, 0), data_collection_group_id=0, grid_ids=(0,)
    )
    with patch(
        "hyperion.experiment_plans.flyscan_xray_centre_plan.XrayCentreCallbackCollection.setup",
        return_value=callbacks,
    ):
        RE(flyscan_xray_centre(fxc_composite, params))
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
    fxc_composite: FlyScanXRayCentreComposite,
    params: GridscanInternalParameters,
    RE: RunEngine,
):
    run_gridscan_and_move.side_effect = Exception()
    with pytest.raises(Exception):
        RE(flyscan_xray_centre(fxc_composite, params))
    set_shutter_to_manual.assert_called_once()


@pytest.mark.s03
def test_GIVEN_scan_invalid_WHEN_plan_run_THEN_ispyb_entry_made_but_no_zocalo_entry(
    RE: RunEngine,
    fxc_composite: FlyScanXRayCentreComposite,
    fetch_comment: Callable,
    params: GridscanInternalParameters,
    callbacks: XrayCentreCallbackCollection,
):
    params.hyperion_params.detector_params.directory = "./tmp"
    params.hyperion_params.detector_params.prefix = str(uuid.uuid1())
    params.hyperion_params.ispyb_params.visit_path = "/dls/i03/data/2022/cm31105-5/"

    # Currently s03 calls anything with z_steps > 1 invalid
    params.experiment_params.z_steps = 100

    mock_start_zocalo = MagicMock()
    callbacks.zocalo_handler.zocalo_interactor.run_start = mock_start_zocalo

    with pytest.raises(WarningException), patch(
        "hyperion.experiment_plans.flyscan_xray_centre_plan.XrayCentreCallbackCollection.from_params",
        lambda _: callbacks,
    ):
        RE(flyscan_xray_centre(fxc_composite, params))

    dcid_used = callbacks.ispyb_handler.ispyb_ids = IspybIds(
        data_collection_ids=(0, 0), data_collection_group_id=0, grid_ids=(0,)
    )
    assert callbacks.ispyb_handler.ispyb.data_collection_ids is not None
    dcid_used = callbacks.ispyb_handler.ispyb.data_collection_ids[0]

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
    fxc_composite: FlyScanXRayCentreComposite,
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

    fxc_composite.eiger.stage = MagicMock()
    fxc_composite.eiger.unstage = MagicMock()

    callbacks = XrayCentreCallbackCollection.setup()
    callbacks.ispyb_handler.ispyb.ISPYB_CONFIG_PATH = ISPYB_CONFIG

    with patch(
        "hyperion.experiment_plans.flyscan_xray_centre_plan.XrayCentreCallbackCollection.from_params",
        lambda _: callbacks,
    ):
        RE(flyscan_xray_centre(fxc_composite, params))

    # The following numbers are derived from the centre returned in fake_zocalo
    assert fxc_composite.sample_motors.x.user_readback.get() == pytest.approx(0.05)
    assert fxc_composite.sample_motors.y.user_readback.get() == pytest.approx(0.15)
    assert fxc_composite.sample_motors.z.user_readback.get() == pytest.approx(0.25)
