from ophyd import Component, FormattedComponent

from artemis.devices.aperturescatterguard import ApertureScatterguard
from artemis.devices.fast_grid_scan import FastGridScan
from artemis.devices.I03Smargon import I03Smargon
from artemis.devices.logging_ophyd_device import InfoLoggingDevice
from artemis.devices.slit_gaps import SlitGaps
from artemis.devices.synchrotron import Synchrotron
from artemis.devices.undulator import Undulator
from artemis.devices.zebra import Zebra
from artemis.parameters import AperturePositions


class FGSComposite(InfoLoggingDevice):
    """A device consisting of all the Devices required for a fast gridscan."""

    fast_grid_scan = Component(FastGridScan, "-MO-SGON-01:FGS:")

    zebra = Component(Zebra, "-EA-ZEBRA-01:")

    undulator = FormattedComponent(Undulator, "{insertion_prefix}-MO-SERVC-01:")

    synchrotron = FormattedComponent(Synchrotron)
    slit_gaps = Component(SlitGaps, "-AL-SLITS-04:")

    sample_motors: I03Smargon = Component(I03Smargon, "")

    aperture_scatterguard: ApertureScatterguard

    def __init__(
        self,
        insertion_prefix: str,
        aperture_positions: AperturePositions,
        *args,
        **kwargs
    ):
        self.insertion_prefix = insertion_prefix
        self.aperture_scatterguard = Component(
            ApertureScatterguard, "", positions=aperture_positions
        )
        super().__init__(*args, **kwargs)
