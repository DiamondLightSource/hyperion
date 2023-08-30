from unittest.mock import MagicMock, patch
from hyperion.utils.aperturescatterguard import load_default_aperture_scatterguard_positions_if_unset, ApertureScatterguard


@patch("hyperion.utils.aperturescatterguard.AperturePositions.from_gda_beamline_params")
def test_if_aperture_scatterguard_positions_unset_then_defaults_loaded(from_gda_beamline_params):
    asg = MagicMock(spec=ApertureScatterguard)
    asg.aperture_positions = None

    load_default_aperture_scatterguard_positions_if_unset(asg)

    asg.load_aperture_positions.assert_called_once_with(from_gda_beamline_params.return_value)


@patch("hyperion.utils.aperturescatterguard.AperturePositions.from_gda_beamline_params")
def test_if_aperture_scatterguard_positions_unset_then_nothing_loaded(from_gda_beamline_params):
    asg = MagicMock(spec=ApertureScatterguard)
    asg.aperture_positions = object()

    load_default_aperture_scatterguard_positions_if_unset(asg)

    asg.load_aperture_positions.assert_not_called()
