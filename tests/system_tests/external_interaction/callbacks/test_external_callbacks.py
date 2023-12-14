from multiprocessing import Process
from time import sleep
from typing import Sequence
from unittest.mock import MagicMock, patch

import pytest
from bluesky.callbacks.zmq import Publisher
from bluesky.run_engine import RunEngine

from hyperion.__main__ import CALLBACK_0MQ_PROXY_PORTS
from hyperion.external_interaction.callbacks.__main__ import (
    HyperionCallbackRunner,
    main,
)
from hyperion.log import ISPYB_LOGGER, NEXUS_LOGGER

from ..conftest import (  # noqa
    fetch_comment,
    zocalo_env,
)


@pytest.mark.s03
@patch("hyperion.external_interaction.callbacks.__main__.parse_cli_args", lambda: ("DEBUG",None,True,None))
def test_dev_ispyb_deposition_made_and_fake_zocalo_results_returned_by_external_callbacks(
    wait_forever: MagicMock,
    RE: RunEngine,
    zocalo_env
):


    remote_callback_and_proxy_process = Process(target=main)
    remote_callback_and_proxy_process.start()



    publisher = Publisher(f"localhost:{CALLBACK_0MQ_PROXY_PORTS[0]}")
    RE.subscribe(publisher)
