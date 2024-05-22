import gzip
import json
import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import bluesky.preprocessors as bpp
from bluesky.run_engine import RunEngine
from dodal.beamlines import i03
from ophyd.status import Status
from ophyd_async.core import set_mock_value

from hyperion.device_setup_plans.read_hardware_for_setup import (
    read_hardware_for_ispyb_during_collection,
    read_hardware_for_nexus_writer,
)
from hyperion.experiment_plans.rotation_scan_plan import RotationScanComposite
from hyperion.external_interaction.callbacks.rotation.nexus_callback import (
    RotationNexusFileCallback,
)
from hyperion.parameters.constants import CONST
from hyperion.parameters.rotation import RotationScan

TEST_DATA_DIRECTORY = Path("tests/test_data/nexus_files/rotation")
TEST_METAFILE = "ins_8_5_meta.h5.gz"
FAKE_DATAFILE = "../fake_data.h5"
FILENAME_STUB = "test_rotation_nexus"


def test_params(filename_stub, dir):
    def get_params(filename):
        with open(filename) as f:
            return json.loads(f.read())

    params = RotationScan(
        **get_params(
            "tests/test_data/parameter_json_files/good_test_rotation_scan_parameters.json"
        )
    )
    params.file_name = filename_stub
    params.scan_width_deg = 360
    params.demand_energy_ev = 12700
    params.storage_directory = str(dir)
    params.x_start_um = 0
    params.y_start_um = 0
    params.z_start_um = 0
    params.exposure_time_s = 0.004
    return params


def fake_rotation_scan(
    parameters: RotationScan,
    subscription: RotationNexusFileCallback,
    rotation_devices: RotationScanComposite,
):
    @bpp.subs_decorator(subscription)
    @bpp.set_run_key_decorator("rotation_scan_with_cleanup_and_subs")
    @bpp.run_decorator(  # attach experiment metadata to the start document
        md={
            "subplan_name": CONST.PLAN.ROTATION_OUTER,
            "hyperion_parameters": parameters.json(),
            "activate_callbacks": "RotationNexusFileCallback",
        }
    )
    def plan():
        yield from read_hardware_for_ispyb_during_collection(
            rotation_devices.attenuator, rotation_devices.flux, rotation_devices.dcm
        )
        yield from read_hardware_for_nexus_writer(rotation_devices.eiger)

    return plan()


def fake_create_rotation_devices():
    eiger = i03.eiger(fake_with_ophyd_sim=True)
    smargon = i03.smargon(fake_with_ophyd_sim=True)
    zebra = i03.zebra(fake_with_ophyd_sim=True)
    detector_motion = i03.detector_motion(fake_with_ophyd_sim=True)
    backlight = i03.backlight(fake_with_ophyd_sim=True)
    attenuator = i03.attenuator(fake_with_ophyd_sim=True)
    flux = i03.flux(fake_with_ophyd_sim=True)
    undulator = i03.undulator(fake_with_ophyd_sim=True)
    aperture_scatterguard = i03.aperture_scatterguard(fake_with_ophyd_sim=True)
    synchrotron = i03.synchrotron(fake_with_ophyd_sim=True)
    s4_slit_gaps = i03.s4_slit_gaps(fake_with_ophyd_sim=True)
    dcm = i03.dcm(fake_with_ophyd_sim=True)
    robot = i03.robot(fake_with_ophyd_sim=True)
    mock_omega_sets = MagicMock(return_value=Status(done=True, success=True))
    mock_omega_velocity_sets = MagicMock(return_value=Status(done=True, success=True))

    smargon.omega.velocity.set = mock_omega_velocity_sets
    smargon.omega.set = mock_omega_sets

    smargon.omega.max_velocity.sim_put(131)  # type: ignore

    set_mock_value(dcm.energy_in_kev.user_readback, 12700)

    return RotationScanComposite(
        attenuator=attenuator,
        backlight=backlight,
        dcm=dcm,
        detector_motion=detector_motion,
        eiger=eiger,
        flux=flux,
        smargon=smargon,
        undulator=undulator,
        aperture_scatterguard=aperture_scatterguard,
        synchrotron=synchrotron,
        s4_slit_gaps=s4_slit_gaps,
        zebra=zebra,
        robot=robot,
    )


def sim_rotation_scan_to_create_nexus(
    test_params: RotationScan,
    fake_create_rotation_devices: RotationScanComposite,
    filename_stub,
    RE,
):
    run_number = test_params.detector_params.run_number
    nexus_filename = f"{filename_stub}_{run_number}.nxs"

    fake_create_rotation_devices.eiger.bit_depth.sim_put(32)  # type: ignore

    with patch(
        "hyperion.external_interaction.nexus.write_nexus.get_start_and_predicted_end_time",
        return_value=("test_time", "test_time"),
    ):
        RE(
            fake_rotation_scan(
                test_params, RotationNexusFileCallback(), fake_create_rotation_devices
            )
        )

    nexus_path = Path(test_params.storage_directory) / nexus_filename
    assert os.path.isfile(nexus_path)
    return filename_stub, run_number


def extract_metafile(input_filename, output_filename):
    with gzip.open(input_filename) as metafile_fo:
        with open(output_filename, "wb") as output_fo:
            output_fo.write(metafile_fo.read())


def _generate_fake_nexus(filename, dir=os.getcwd()):
    RE = RunEngine({})
    params = test_params(filename, dir)
    run_number = params.detector_params.run_number
    filename_stub, run_number = sim_rotation_scan_to_create_nexus(
        params, fake_create_rotation_devices(), filename, RE
    )
    return filename_stub, run_number


def generate_test_nexus():
    filename_stub, run_number = _generate_fake_nexus(FILENAME_STUB)
    # ugly hack because we get double free error on exit
    with open("OUTPUT_FILENAME", "x") as f:
        f.write(f"{filename_stub}_{run_number}.nxs")

    extract_metafile(
        str(TEST_DATA_DIRECTORY / TEST_METAFILE),
        f"{FILENAME_STUB}_{run_number}_meta.h5",
    )

    new_hyp_data = [f"{FILENAME_STUB}_{run_number}_00000{n}.h5" for n in [1, 2, 3, 4]]
    [shutil.copy(TEST_DATA_DIRECTORY / FAKE_DATAFILE, d) for d in new_hyp_data]

    exit(0)


def copy_test_meta_data_files():
    extract_metafile(
        str(TEST_DATA_DIRECTORY / TEST_METAFILE),
        f"{TEST_DATA_DIRECTORY}/ins_8_5_meta.h5",
    )
    new_data = [f"{TEST_DATA_DIRECTORY}/ins_8_5_00000{n}.h5" for n in [1, 2, 3, 4]]
    [shutil.copy(TEST_DATA_DIRECTORY / FAKE_DATAFILE, d) for d in new_data]


if __name__ == "__main__":
    generate_test_nexus()
