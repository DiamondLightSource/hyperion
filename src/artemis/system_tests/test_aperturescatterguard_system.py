import pytest
from dodal.devices.aperturescatterguard import AperturePositions, ApertureScatterguard

from artemis.parameters.beamline_parameters import GDABeamlineParameters
from artemis.parameters.constants import I03_BEAMLINE_PARAMETER_PATH


@pytest.fixture
def ap_sg():
    ap_sg = ApertureScatterguard(prefix="BL03S", name="ap_sg")
    ap_sg.load_aperture_positions(
        AperturePositions.from_gda_beamline_params(
            GDABeamlineParameters.from_file(I03_BEAMLINE_PARAMETER_PATH)
        )
    )
    return ap_sg


@pytest.mark.s03()
def test_aperture_change_callback(ap_sg: ApertureScatterguard):
    from bluesky.run_engine import RunEngine

    from artemis.experiment_plans.fast_grid_scan_plan import set_aperture_for_bbox_size
    from artemis.external_interaction.callbacks.aperture_change_callback import (
        ApertureChangeCallback,
    )

    cb = ApertureChangeCallback()
    RE = RunEngine({})
    RE.subscribe(cb)
    RE(set_aperture_for_bbox_size(ap_sg, [2, 2, 2]))
    assert cb.last_selected_aperture == "LARGE_APERTURE"
