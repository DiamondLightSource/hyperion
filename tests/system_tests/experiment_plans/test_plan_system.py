import bluesky.preprocessors as bpp
import pytest
from bluesky.run_engine import RunEngine
from dodal.beamlines import i03
from dodal.devices.s4_slit_gaps import S4SlitGaps
from dodal.devices.undulator import Undulator

from hyperion.device_setup_plans.read_hardware_for_setup import (
    read_hardware_for_ispyb_during_collection,
    read_hardware_for_ispyb_pre_collection,
)
from hyperion.parameters.constants import SIM_BEAMLINE, SIM_INSERTION_PREFIX


@pytest.mark.s03
def test_getting_data_for_ispyb():
    undulator = Undulator(f"{SIM_INSERTION_PREFIX}-MO-SERVC-01:", name="undulator")
    synchrotron = i03.synchrotron(fake_with_ophyd_sim=True)
    slit_gaps = S4SlitGaps(f"{SIM_BEAMLINE}-AL-SLITS-04:", name="slits")
    attenuator = i03.attenuator(fake_with_ophyd_sim=True)
    flux = i03.flux(fake_with_ophyd_sim=True)
    dcm = i03.dcm(fake_with_ophyd_sim=True)
    robot = i03.robot(fake_with_ophyd_sim=True)

    RE = RunEngine()

    @bpp.run_decorator()
    def standalone_read_hardware(und, syn, slits, robot, att, flux):
        yield from read_hardware_for_ispyb_pre_collection(und, syn, slits, robot)
        yield from read_hardware_for_ispyb_during_collection(att, flux, dcm)

    RE(
        standalone_read_hardware(
            undulator, synchrotron, slit_gaps, robot, attenuator, flux
        )
    )
