import bluesky.plan_stubs as bps
from bluesky.run_engine import RunEngine
from dodal.beamlines.beamline_utils import device_instantiation
from dodal.beamlines.i03 import dcm, undulator
from dodal.devices.DCM import DCM
from dodal.devices.undulator import Undulator
from dodal.devices.undulator_dcm import UndulatorDCM


def change_energy_plan(undulator_dcm: UndulatorDCM, energy):
    yield from bps.abs_set(undulator_dcm.energy_kev, energy)


if __name__ == "main":
    und: Undulator = undulator()
    d: DCM = dcm()
    RE = RunEngine()

    undulator_dcm = device_instantiation(
        UndulatorDCM(und, d),
        "undulator_dcm",
        "",
        False,
        False,
        bl_prefix=False,
    )

    RE(change_energy_plan(undulator_dcm, 13700))
