from dodal.common.beamlines.beamline_parameters import get_beamline_parameters
from dodal.devices.aperturescatterguard import AperturePositions, ApertureScatterguard


def load_default_aperture_scatterguard_positions_if_unset(
    aperture_scatterguard: ApertureScatterguard,
) -> None:
    """
    If aperture scatterguard positions are `None`, load the default set of positions.

    If the positions are already set, do nothing.
    """
    if aperture_scatterguard.aperture_positions is None:
        params = get_beamline_parameters()
        aperture_positions = AperturePositions.from_gda_beamline_params(params)
        aperture_scatterguard.load_aperture_positions(aperture_positions)
