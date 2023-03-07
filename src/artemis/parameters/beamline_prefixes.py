from dataclasses import dataclass
from os import environ

from artemis.parameters.constants import SIM_BEAMLINE, SIM_INSERTION_PREFIX


@dataclass
class BeamlinePrefixes:
    beamline_prefix: str
    insertion_prefix: str


def get_beamline_prefixes():
    beamline = environ.get("BEAMLINE")
    if beamline is None:
        return BeamlinePrefixes(SIM_BEAMLINE, SIM_INSERTION_PREFIX)
    if beamline == "i03":
        return BeamlinePrefixes("BL03I", "SR03I")
    else:
        raise Exception(f"Beamline {beamline} is not currently supported by Artemis")
