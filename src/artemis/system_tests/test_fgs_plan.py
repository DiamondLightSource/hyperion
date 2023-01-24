from unittest.mock import MagicMock, patch

import bluesky.preprocessors as bpp
import pytest
from bluesky.run_engine import RunEngine

from artemis.devices.eiger import EigerDetector
from artemis.devices.fast_grid_scan_composite import FGSComposite
from artemis.experiment_plans.fast_grid_scan_plan import (
    get_plan,
    read_hardware_for_ispyb,
    run_gridscan,
)
from artemis.external_interaction.callbacks import FGSCallbackCollection
from artemis.parameters import SIM_BEAMLINE, DetectorParams, FullParameters


@pytest.fixture()
def eiger() -> EigerDetector:
    detector_params: DetectorParams = DetectorParams(
        current_energy=100,
        exposure_time=0.1,
        directory="/tmp",
        prefix="file_name",
        detector_distance=100.0,
        omega_start=0.0,
        omega_increment=0.1,
        num_images=50,
        use_roi_mode=False,
        run_number=0,
        det_dist_to_beam_converter_path="src/artemis/devices/unit_tests/test_lookup_table.txt",
    )
    eiger = EigerDetector(
        detector_params=detector_params, name="eiger", prefix="BL03S-EA-EIGER-01:"
    )

    # Otherwise odin moves too fast to be tested
    eiger.cam.manual_trigger.put("Yes")

    # S03 currently does not have StaleParameters_RBV
    eiger.wait_for_stale_parameters = lambda: None
    eiger.odin.check_odin_initialised = lambda: (True, "")

    yield eiger


params = FullParameters()
params.beamline = SIM_BEAMLINE


@pytest.fixture
def RE():
    return RunEngine({})


@pytest.fixture
def fgs_composite():
    fast_grid_scan_composite = FGSComposite(
        insertion_prefix=params.insertion_prefix,
        name="fgs",
        prefix=params.beamline,
    )
    return fast_grid_scan_composite


@pytest.mark.skip("Broken due to eiger issues in s03")
@pytest.mark.s03
@patch("artemis.fast_grid_scan_plan.wait_for_fgs_valid")
@patch("bluesky.plan_stubs.wait")
@patch("bluesky.plan_stubs.kickoff")
@patch("bluesky.plan_stubs.complete")
def test_run_gridscan(
    wait_for_fgs_valid: MagicMock,
    complete: MagicMock,
    kickoff: MagicMock,
    wait: MagicMock,
    eiger: EigerDetector,
    RE: RunEngine,
    fgs_composite: FGSComposite,
):
    eiger.unstage = lambda: True
    fgs_composite.wait_for_connection()
    # Would be better to use get_plan instead but eiger doesn't work well in S03
    RE(run_gridscan(fgs_composite, eiger, params))


@pytest.mark.s03
def test_read_hardware_for_ispyb(
    eiger: EigerDetector,
    RE: RunEngine,
    fgs_composite: FGSComposite,
):

    undulator = fgs_composite.undulator
    synchrotron = fgs_composite.synchrotron
    slit_gaps = fgs_composite.slit_gaps

    @bpp.run_decorator()
    def read_run(u, s, g):
        yield from read_hardware_for_ispyb(u, s, g)

    fgs_composite.wait_for_connection()
    RE(read_run(undulator, synchrotron, slit_gaps))


@pytest.mark.s03
@patch("bluesky.plan_stubs.wait")
@patch("bluesky.plan_stubs.kickoff")
@patch("bluesky.plan_stubs.complete")
@patch("artemis.fast_grid_scan_plan.run_gridscan_and_move")
@patch("artemis.fast_grid_scan_plan.set_zebra_shutter_to_manual")
def test_full_plan_tidies_at_end(
    set_shutter_to_manual: MagicMock,
    run_gridscan_and_move: MagicMock,
    complete: MagicMock,
    kickoff: MagicMock,
    wait: MagicMock,
    eiger: EigerDetector,
    RE: RunEngine,
    fgs_composite: FGSComposite,
):
    callbacks = FGSCallbackCollection.from_params(FullParameters())
    RE(get_plan(params, callbacks))
    set_shutter_to_manual.assert_called_once()


@pytest.mark.s03
@patch("bluesky.plan_stubs.wait")
@patch("bluesky.plan_stubs.kickoff")
@patch("bluesky.plan_stubs.complete")
@patch("artemis.fast_grid_scan_plan.run_gridscan_and_move")
@patch("artemis.fast_grid_scan_plan.set_zebra_shutter_to_manual")
def test_full_plan_tidies_at_end_when_plan_fails(
    set_shutter_to_manual: MagicMock,
    run_gridscan_and_move: MagicMock,
    complete: MagicMock,
    kickoff: MagicMock,
    wait: MagicMock,
    eiger: EigerDetector,
    RE: RunEngine,
    fgs_composite: FGSComposite,
):
    callbacks = FGSCallbackCollection.from_params(FullParameters())
    run_gridscan_and_move.side_effect = Exception()
    with pytest.raises(Exception):
        RE(get_plan(params, callbacks))
    set_shutter_to_manual.assert_called_once()
    # tidy_plans.assert_called_once()
