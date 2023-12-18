from multiprocessing import Process
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from bluesky.callbacks.zmq import Publisher
from bluesky.run_engine import RunEngine
from dodal.devices.zocalo import ZocaloResults

from hyperion.__main__ import CALLBACK_0MQ_PROXY_PORTS
from hyperion.experiment_plans.flyscan_xray_centre_plan import (
    FlyScanXRayCentreComposite,
    flyscan_xray_centre,
)
from hyperion.external_interaction.callbacks.__main__ import (
    main,
)
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)

from ..conftest import (  # noqa
    fetch_comment,
    zocalo_env,
)


@pytest_asyncio.fixture
async def zocalo_device():
    zd = ZocaloResults()
    zd.timeout_s = 10
    await zd.connect()
    return zd


@pytest.mark.s03
@patch(
    "hyperion.external_interaction.callbacks.__main__.parse_cli_args",
    lambda: ("DEBUG", None, True, None),
)
def test_dev_ispyb_deposition_made_and_fake_zocalo_results_returned_by_external_callbacks(
    RE: RunEngine,
    zocalo_env,
    test_fgs_params: GridscanInternalParameters,
    fake_fgs_composite: FlyScanXRayCentreComposite,
    done_status,
    zocalo_device,
):
    """This test doesn't actually require S03 to be running, but it does require fake
    zocalo, and a connection to the dev ISPyB database; like S03 tests, it can only run
    locally at DLS."""

    remote_callback_and_proxy_process = Process(target=main)
    remote_callback_and_proxy_process.start()
    test_fgs_params.hyperion_params.zocalo_environment = "dev_artemis"

    try:
        fake_fgs_composite.aperture_scatterguard.aperture.z.user_setpoint.sim_put(  # type: ignore
            2
        )
        fake_fgs_composite.eiger.unstage = MagicMock(return_value=done_status)  # type: ignore
        fake_fgs_composite.smargon.stub_offsets.set = MagicMock(return_value=done_status)  # type: ignore
        fake_fgs_composite.zocalo = zocalo_device
        publisher = Publisher(f"localhost:{CALLBACK_0MQ_PROXY_PORTS[0]}")
        RE.subscribe(publisher)

        RE(flyscan_xray_centre(fake_fgs_composite, test_fgs_params))
    finally:
        remote_callback_and_proxy_process.terminate()
        remote_callback_and_proxy_process.close()
