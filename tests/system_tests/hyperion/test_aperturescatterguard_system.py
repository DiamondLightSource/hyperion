import pytest
from dodal.common.beamlines.beamline_parameters import (
    BEAMLINE_PARAMETER_PATHS,
    GDABeamlineParameters,
)
from dodal.devices.aperturescatterguard import (
    ApertureScatterguard,
    load_positions_from_beamline_parameters,
    load_tolerances_from_beamline_params,
)
from ophyd_async.core import DeviceCollector


@pytest.fixture
def ap_sg():
    params = GDABeamlineParameters.from_file(BEAMLINE_PARAMETER_PATHS["i03"])
    with DeviceCollector():
        ap_sg = ApertureScatterguard(
            prefix="BL03S",
            name="ap_sg",
            loaded_positions=load_positions_from_beamline_parameters(params),
            tolerances=load_tolerances_from_beamline_params(params),
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

    cb = ApertureChangeCallback()
    RE = RunEngine({})
    RE.subscribe(cb)
    RE(set_aperture_for_bbox_size(ap_sg, [2, 2, 2]))
    assert cb.last_selected_aperture == "LARGE_APERTURE"
