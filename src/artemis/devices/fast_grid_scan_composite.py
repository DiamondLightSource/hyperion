from ophyd import Component, Device, FormattedComponent

from src.artemis.devices.fast_grid_scan import FastGridScan
from src.artemis.devices.slit_gaps import SlitGaps
from src.artemis.devices.synchrotron import Synchrotron
from src.artemis.devices.undulator import Undulator
from src.artemis.devices.zebra import Zebra


class FGSComposite(Device):
    """A device consisting of all the Devices required for a fast gridscan."""

    fast_grid_scan = Component(FastGridScan, "-MO-SGON-01:FGS:")

    zebra = Component(Zebra, "-EA-ZEBRA-01:")

    undulator = FormattedComponent(Undulator, "{insertion_prefix}-MO-SERVC-01:")

    synchrotron = FormattedComponent(Synchrotron)
    slit_gaps = Component(SlitGaps, "-AL-SLITS-04:")

    def __init__(self, insertion_prefix: str, *args, **kwargs):
        self.insertion_prefix = insertion_prefix
        super().__init__(*args, **kwargs)
