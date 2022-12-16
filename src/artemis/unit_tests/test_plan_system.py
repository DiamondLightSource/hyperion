import bluesky.preprocessors as bpp
import pytest
from bluesky import RunEngine

from artemis.devices.slit_gaps import SlitGaps
from artemis.devices.synchrotron import Synchrotron
from artemis.devices.undulator import Undulator
from artemis.fast_grid_scan_plan import read_hardware_for_ispyb
from artemis.parameters import SIM_BEAMLINE, SIM_INSERTION_PREFIX


@pytest.mark.s03
def test_getting_data_for_ispyb():
    undulator = Undulator(f"{SIM_INSERTION_PREFIX}-MO-SERVC-01:", name="undulator")
    synchrotron = Synchrotron(name="synch")
    slit_gaps = SlitGaps(f"{SIM_BEAMLINE}-AL-SLITS-04:", name="slits")

    undulator.wait_for_connection()
    synchrotron.wait_for_connection()
    slit_gaps.wait_for_connection()

    RE = RunEngine()

    @bpp.run_decorator()
    def standalone_read_hardware_for_ispyb(und, syn, slits):
        yield from read_hardware_for_ispyb(und, syn, slits)

    RE(standalone_read_hardware_for_ispyb(undulator, synchrotron, slit_gaps))
