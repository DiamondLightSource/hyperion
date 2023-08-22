import bluesky.preprocessors as bpp
import pytest
from bluesky import RunEngine
from dodal.devices.s4_slit_gaps import S4SlitGaps
from dodal.devices.synchrotron import Synchrotron
from dodal.devices.undulator import Undulator

from hyperion.experiment_plans.flyscan_xray_centre_plan import read_hardware_for_ispyb
from hyperion.parameters.constants import SIM_BEAMLINE, SIM_INSERTION_PREFIX


@pytest.mark.s03
def test_getting_data_for_ispyb():
    undulator = Undulator(f"{SIM_INSERTION_PREFIX}-MO-SERVC-01:", name="undulator")
    synchrotron = Synchrotron(name="synch")
    slit_gaps = S4SlitGaps(f"{SIM_BEAMLINE}-AL-SLITS-04:", name="slits")

    undulator.wait_for_connection()
    synchrotron.wait_for_connection()
    slit_gaps.wait_for_connection()

    RE = RunEngine()

    @bpp.run_decorator()
    def standalone_read_hardware_for_ispyb(und, syn, slits):
        yield from read_hardware_for_ispyb(und, syn, slits)

    RE(standalone_read_hardware_for_ispyb(undulator, synchrotron, slit_gaps))
