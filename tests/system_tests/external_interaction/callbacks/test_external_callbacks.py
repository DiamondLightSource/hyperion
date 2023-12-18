from multiprocessing import Process
from unittest.mock import patch

import pytest
from bluesky.callbacks.zmq import Publisher
from bluesky.run_engine import RunEngine

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
):
    remote_callback_and_proxy_process = Process(target=main)
    remote_callback_and_proxy_process.start()

    publisher = Publisher(f"localhost:{CALLBACK_0MQ_PROXY_PORTS[0]}")
    RE.subscribe(publisher)

    RE(flyscan_xray_centre(fake_fgs_composite, test_fgs_params))
