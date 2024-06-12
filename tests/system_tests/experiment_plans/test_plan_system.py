import bluesky.preprocessors as bpp
import pytest
from bluesky.run_engine import RunEngine
from dodal.beamlines import i03
from dodal.devices.aperturescatterguard import ApertureScatterguard
from dodal.devices.slits import Slits
from dodal.devices.undulator import Undulator

from hyperion.device_setup_plans.read_hardware_for_setup import (
    read_hardware_for_ispyb_during_collection,
    read_hardware_for_ispyb_pre_collection,
)
from hyperion.parameters.constants import CONST


@pytest.mark.s03
@pytest.mark.asyncio
async def test_getting_data_for_ispyb():
    undulator = Undulator(
        f"{CONST.SIM.INSERTION_PREFIX}-MO-SERVC-01:", name="undulator"
    )
    synchrotron = i03.synchrotron(fake_with_ophyd_sim=True)
    slit_gaps = Slits(f"{CONST.SIM.BEAMLINE}-AL-SLITS-04:", name="slits")
    attenuator = i03.attenuator(fake_with_ophyd_sim=True)
    flux = i03.flux(fake_with_ophyd_sim=True)
    dcm = i03.dcm(fake_with_ophyd_sim=True)
    aperture_scatterguard = ApertureScatterguard(
        prefix=f"{CONST.SIM.BEAMLINE}-AL-APSG-04:", name="ao_sg"
    )
    smargon = i03.smargon(fake_with_ophyd_sim=True)

    await undulator.connect()
    await synchrotron.connect()
    await slit_gaps.connect()
    attenuator.wait_for_connection()
    flux.wait_for_connection()
    aperture_scatterguard.wait_for_connection()
    smargon.wait_for_connection()
    robot = i03.robot(fake_with_ophyd_sim=True)

    RE = RunEngine()

    @bpp.run_decorator()
    def standalone_read_hardware(und, syn, slits, robot, att, flux, ap_sg, sm):
        yield from read_hardware_for_ispyb_pre_collection(
            und, syn, slits, robot, ap_sg, smargon=sm
        )
        yield from read_hardware_for_ispyb_during_collection(att, flux, dcm)

    RE(
        standalone_read_hardware(
            undulator,
            synchrotron,
            slit_gaps,
            robot,
            attenuator,
            flux,
            aperture_scatterguard,
            smargon,
        )
    )
