import pytest
from dodal.beamlines.beamline_parameters import (
    BEAMLINE_PARAMETER_PATHS,
    GDABeamlineParameters,
)
from dodal.devices.aperturescatterguard import AperturePositions, ApertureScatterguard


@pytest.fixture
def ap_sg():
    ap_sg = ApertureScatterguard(prefix="BL03S", name="ap_sg")
    ap_sg.load_aperture_positions(
        AperturePositions.from_gda_beamline_params(
            GDABeamlineParameters.from_file(BEAMLINE_PARAMETER_PATHS["i03"])
        )
    )
    return ap_sg


@pytest.mark.s03()
def test_aperture_change_callback(ap_sg: ApertureScatterguard):
    from bluesky.run_engine import RunEngine

    from hyperion.experiment_plans.flyscan_xray_centre_plan import (
        set_aperture_for_bbox_size,
    )
    from hyperion.external_interaction.callbacks.aperture_change_callback import (
        ApertureChangeCallback,
    )

    ap_sg.wait_for_connection()
    cb = ApertureChangeCallback()
    RE = RunEngine({})
    RE.subscribe(cb)
    RE(set_aperture_for_bbox_size(ap_sg, [2, 2, 2]))
    assert cb.last_selected_aperture == "LARGE_APERTURE"
