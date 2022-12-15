from ophyd import Component, Device, FormattedComponent
from ophyd.log import logger as ophyd_logger

from artemis.devices.fast_grid_scan import FastGridScan
from artemis.devices.I03Smargon import I03Smargon
from artemis.devices.slit_gaps import SlitGaps
from artemis.devices.synchrotron import Synchrotron
from artemis.devices.undulator import Undulator
from artemis.devices.zebra import Zebra


class FGSComposite(Device):
    """A device consisting of all the Devices required for a fast gridscan."""

    fast_grid_scan = Component(FastGridScan, "-MO-SGON-01:FGS:")

    zebra = Component(Zebra, "-EA-ZEBRA-01:")

    undulator = FormattedComponent(Undulator, "{insertion_prefix}-MO-SERVC-01:")

    synchrotron = FormattedComponent(Synchrotron)
    slit_gaps = Component(SlitGaps, "-AL-SLITS-04:")

    sample_motors: I03Smargon = Component(I03Smargon, "")

    def __init__(self, insertion_prefix: str, *args, **kwargs):
        self.insertion_prefix = insertion_prefix
        super().__init__(*args, **kwargs)

    def wait_for_connection(self, all_signals=False, timeout=2):
        ophyd_logger.info(
            f"FGSComposite waiting for connection, {'not' if all_signals else ''} waiting for all signals, timeout = {timeout}s.",
        )
        try:
            super().wait_for_connection(all_signals, timeout)
        except TimeoutError as e:
            ophyd_logger.error("FGSComposite failed to connect.", exc_info=True)
            raise e
        else:
            ophyd_logger.info("FGSComposite connected.", exc_info=True)
