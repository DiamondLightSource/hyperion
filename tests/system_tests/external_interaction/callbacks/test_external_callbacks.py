from __future__ import annotations

import os
import re
import signal
import subprocess
import threading
from time import sleep
from unittest.mock import MagicMock, patch

import bluesky.plan_stubs as bps
import numpy as np
import pytest
import pytest_asyncio
import zmq
from bluesky.callbacks import CallbackBase
from bluesky.callbacks.zmq import Publisher
from bluesky.run_engine import RunEngine
from dodal.devices.zocalo import ZocaloResults
from genericpath import isfile
from zmq.utils.monitor import recv_monitor_message

from hyperion.__main__ import CALLBACK_0MQ_PROXY_PORTS
from hyperion.experiment_plans.flyscan_xray_centre_plan import (
    FlyScanXRayCentreComposite,
    flyscan_xray_centre,
)
from hyperion.experiment_plans.rotation_scan_plan import (
    RotationScanComposite,
    rotation_scan,
)
from hyperion.log import LOGGER
from hyperion.parameters.constants import (
    CALLBACK_0MQ_PROXY_PORTS,
    DEV_ISPYB_DATABASE_CFG,
)
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)
from hyperion.utils.utils import convert_angstrom_to_eV

from ....conftest import fake_read
from ..conftest import (  # noqa
    fetch_comment,
    zocalo_env,
)


@pytest_asyncio.fixture
async def zocalo_device():
    zd = ZocaloResults()
    zd.timeout_s = 5
    await zd.connect()
    return zd


class DocumentCatcher(CallbackBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start = MagicMock()
        self.descriptor = MagicMock()
        self.event = MagicMock()
        self.stop = MagicMock()


def event_monitor(monitor: zmq.Socket, connection_active_lock: threading.Lock) -> None:
    while monitor.poll():
        monitor_event = recv_monitor_message(monitor)
        LOGGER.info(f"Event: {monitor_event}")
        if monitor_event["event"] == zmq.EVENT_CONNECTED:
            LOGGER.info("CONNECTED - acquiring connection_active_lock")
            connection_active_lock.acquire()
        if monitor_event["event"] == zmq.EVENT_MONITOR_STOPPED:
            break
    connection_active_lock.release()
    monitor.close()
    LOGGER.info("event monitor thread done!")


@pytest.fixture
def RE_with_external_callbacks():
    RE = RunEngine()
    old_ispyb_config = os.environ.get("ISPYB_CONFIG_PATH")

    process_env = os.environ.copy()
    process_env["ISPYB_CONFIG_PATH"] = DEV_ISPYB_DATABASE_CFG

    external_callbacks_process = subprocess.Popen(
        [
            "python",
            "src/hyperion/external_interaction/callbacks/__main__.py",
            "--logging-level",
            "DEBUG",
            "--dev",
        ],
        env=process_env,
    )
    publisher = Publisher(f"localhost:{CALLBACK_0MQ_PROXY_PORTS[0]}")
    monitor = publisher._socket.get_monitor_socket()

    connection_active_lock = threading.Lock()
    t = threading.Thread(target=event_monitor, args=(monitor, connection_active_lock))
    t.start()

    while not connection_active_lock.locked():
        sleep(0.1)  # wait for connection to happen before continuing

    sub_id = RE.subscribe(publisher)

    yield RE

    RE.unsubscribe(sub_id)
    publisher.close()

    external_callbacks_process.send_signal(signal.SIGINT)
    sleep(0.01)
    external_callbacks_process.kill()
    t.join()
    if old_ispyb_config:
        os.environ["ISPYB_CONFIG_PATH"] = old_ispyb_config
    else:
        del os.environ["ISPYB_CONFIG_PATH"]


@pytest.mark.s03
def test_RE_with_external_callbacks_starts_and_stops(
    RE_with_external_callbacks: RunEngine,
):
    RE = RE_with_external_callbacks

    def plan():
        yield from bps.sleep(1)

    RE(plan())


@pytest.mark.asyncio
@pytest.mark.s03
async def test_external_callbacks_handle_gridscan_ispyb_and_zocalo(
    RE_with_external_callbacks: RunEngine,
    zocalo_env,
    test_fgs_params: GridscanInternalParameters,
    fake_fgs_composite: FlyScanXRayCentreComposite,
    done_status,
    zocalo_device: ZocaloResults,
    fetch_comment,
):
    """This test doesn't actually require S03 to be running, but it does require fake
    zocalo, and a connection to the dev ISPyB database; like S03 tests, it can only run
    locally at DLS."""

    RE = RE_with_external_callbacks
    test_fgs_params.hyperion_params.zocalo_environment = "dev_artemis"

    fake_fgs_composite.aperture_scatterguard.aperture.z.user_setpoint.sim_put(  # type: ignore
        2
    )
    fake_fgs_composite.eiger.unstage = MagicMock(return_value=done_status)  # type: ignore
    fake_fgs_composite.smargon.stub_offsets.set = MagicMock(return_value=done_status)  # type: ignore
    fake_fgs_composite.zocalo = zocalo_device

    doc_catcher = DocumentCatcher()
    RE.subscribe(doc_catcher)

    # Run the xray centring plan
    RE(flyscan_xray_centre(fake_fgs_composite, test_fgs_params))

    # Check that we we mitted a valid reading from the zocalo device
    zocalo_event = doc_catcher.event.call_args.args[0]["data"]  # type: ignore
    assert np.all(zocalo_event["zocalo-centres_of_mass"][0] == [1, 2, 3])
    assert np.all(zocalo_event["zocalo-bbox_sizes"][0] == [6, 6, 5])

    # get dcids from zocalo device
    dcid_reading = await zocalo_device.ispyb_dcid.read()
    dcgid_reading = await zocalo_device.ispyb_dcgid.read()

    dcid = dcid_reading["zocalo-ispyb_dcid"]["value"]
    dcgid = dcgid_reading["zocalo-ispyb_dcgid"]["value"]

    assert dcid != 0
    assert dcgid != 0

    # check the data in dev ispyb corresponding to this "collection"
    ispyb_comment = fetch_comment(dcid)
    assert ispyb_comment != ""
    assert "Diffraction grid scan of 40 by 20 images" in ispyb_comment
    assert "Zocalo processing took" in ispyb_comment
    assert "Position (grid boxes) ['1', '2', '3']" in ispyb_comment
    assert "Size (grid boxes) [6 6 5];" in ispyb_comment


@pytest.mark.s03()
def test_remote_callbacks_write_to_dev_ispyb_for_rotation(
    RE_with_external_callbacks: RunEngine,
    test_rotation_params: RotationInternalParameters,
    fetch_comment,
    fetch_datacollection_attribute,
    undulator,
    attenuator,
    synchrotron,
    s4_slit_gaps,
    flux,
    fake_create_devices,
):
    test_wl = 0.71
    test_bs_x = 0.023
    test_bs_y = 0.047
    test_exp_time = 0.023
    test_img_wid = 0.27

    test_rotation_params.experiment_params.image_width = test_img_wid
    test_rotation_params.hyperion_params.ispyb_params.beam_size_x = test_bs_x
    test_rotation_params.hyperion_params.ispyb_params.beam_size_y = test_bs_y
    test_rotation_params.hyperion_params.detector_params.exposure_time = test_exp_time
    test_rotation_params.hyperion_params.ispyb_params.current_energy_ev = (
        convert_angstrom_to_eV(test_wl)
    )
    test_rotation_params.hyperion_params.detector_params.current_energy_ev = (
        convert_angstrom_to_eV(test_wl)
    )

    composite = RotationScanComposite(
        attenuator=attenuator,
        backlight=fake_create_devices["backlight"],
        detector_motion=fake_create_devices["detector_motion"],
        eiger=fake_create_devices["eiger"],
        flux=flux,
        smargon=fake_create_devices["smargon"],
        undulator=undulator,
        synchrotron=synchrotron,
        s4_slit_gaps=s4_slit_gaps,
        zebra=fake_create_devices["zebra"],
    )

    with patch("bluesky.preprocessors.__read_and_stash_a_motor", fake_read):
        RE_with_external_callbacks(
            rotation_scan(
                composite,
                test_rotation_params,
            )
        )

    sleep(1)
    assert isfile("tmp/dev/hyperion_ispyb_callback.txt")
    ispyb_log_tail = subprocess.run(
        ["tail", "tmp/dev/hyperion_ispyb_callback.txt"],
        timeout=1,
        stdout=subprocess.PIPE,
    ).stdout.decode("utf-8")

    ids_re = re.compile(r"data_collection_ids=(\d+) data_collection_group_id=(\d+) ")
    matches = ids_re.findall(ispyb_log_tail)

    dcid = matches[0][0]

    comment = fetch_comment(dcid)
    assert comment == "Hyperion rotation scan"
    wavelength = fetch_datacollection_attribute(dcid, "wavelength")
    beamsize_x = fetch_datacollection_attribute(dcid, "beamSizeAtSampleX")
    beamsize_y = fetch_datacollection_attribute(dcid, "beamSizeAtSampleY")
    exposure = fetch_datacollection_attribute(dcid, "exposureTime")

    assert wavelength == test_wl
    assert beamsize_x == test_bs_x
    assert beamsize_y == test_bs_y
    assert exposure == test_exp_time
