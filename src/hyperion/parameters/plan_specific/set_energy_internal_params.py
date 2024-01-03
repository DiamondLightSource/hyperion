from dodal.beamlines.beamline_parameters import (
    get_beamline_parameters,
)


class SetEnergyInternalParameters:
    def __init__(self):
        self.beamline_parameters = get_beamline_parameters()
