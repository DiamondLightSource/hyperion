from unittest.mock import patch

import pytest
from bluesky.run_engine import RunEngine
from dodal.devices.aperturescatterguard import AperturePositions
from ophyd.status import Status

import artemis.experiment_plans.fast_grid_scan_plan as fgs_plan
from artemis.experiment_plans.fast_grid_scan_plan import FGSComposite
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
    # TODO remove fake device patch when flux PV is added
    # https://github.com/DiamondLightSource/python-artemis/issues/822
    from dodal.devices.flux import Flux
    from ophyd.sim import make_fake_device

    FakeFlux = make_fake_device(Flux)

    arm_status = Status()
    arm_status.set_finished()

    with patch("dodal.beamlines.i03.Flux", FakeFlux):
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

    fast_grid_scan_composite.eiger.odin.check_odin_initialised = lambda: (True, "")
    fast_grid_scan_composite.eiger.async_stage = lambda: arm_status
    fast_grid_scan_composite.eiger.unstage = lambda: True
    fast_grid_scan_composite.aperture_scatterguard.scatterguard.x.set_lim(-4.8, 5.7)

    def fake_complete():
        comp_status = Status()
        comp_status.set_finished()
        return comp_status

    fast_grid_scan_composite.fast_grid_scan.complete = fake_complete  # type: ignore
    fast_grid_scan_composite.fast_grid_scan.position_counter.set(0)
    return fast_grid_scan_composite
