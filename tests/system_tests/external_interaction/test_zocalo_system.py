import re

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import numpy as np
import pytest
import pytest_asyncio
from bluesky.run_engine import RunEngine
from dodal.devices.zocalo import ZOCALO_READING_PLAN_NAME, ZocaloResults

from hyperion.external_interaction.callbacks.common.callback_util import (
    create_gridscan_callbacks,
)
from hyperion.external_interaction.callbacks.xray_centre.ispyb_callback import (
    ispyb_activation_wrapper,
)
from hyperion.parameters.constants import CONST
from hyperion.parameters.gridscan import ThreeDGridScan
from tests.conftest import create_dummy_scan_spec

"""
If fake-zocalo system tests are failing, check that the RMQ instance is set up right:

- Open the RMQ webpage specified when you start the fake zocalo and login with the
provided credentials

- go to the admin panel and under the 'exchanges' tab ensure that there is a 'results'
exchange for the zocalo vhost (other settings can be left blank)

- go to the 'queues and streams' tab and add a binding for the xrc.i03 queue to the
results exchange, with the routing key 'xrc.i03'

- make sure that there are no un-acked/un-delivered messages on the i03.xrc queue
"""


@pytest_asyncio.fixture
async def zocalo_device():
    zd = ZocaloResults()
    zd.timeout_s = 10
    await zd.connect()
    return zd


@bpp.set_run_key_decorator("testing125")
@bpp.run_decorator(
    md={
        "subplan_name": CONST.PLAN.DO_FGS,
        "zocalo_environment": "dev_artemis",
        "scan_points": create_dummy_scan_spec(10, 20, 30),
    }
)
def fake_fgs_plan():
    yield from bps.sleep(0)


@pytest.fixture
def run_zocalo_with_dev_ispyb(
    dummy_params: ThreeDGridScan,
    dummy_ispyb_3d,
    RE: RunEngine,
    zocalo_device: ZocaloResults,
):
    async def inner(sample_name="", fallback=np.array([0, 0, 0])):
        dummy_params.file_name = sample_name
        _, ispyb_callback = create_gridscan_callbacks()
        ispyb_callback.ispyb_config = dummy_ispyb_3d.ISPYB_CONFIG_PATH
        RE.subscribe(ispyb_callback)

        @bpp.set_run_key_decorator("testing123")
        def trigger_zocalo_after_fast_grid_scan():
            @bpp.set_run_key_decorator("testing124")
            @bpp.stage_decorator([zocalo_device])
            @bpp.run_decorator(
                md={
                    "subplan_name": CONST.PLAN.GRIDSCAN_OUTER,
                    CONST.TRIGGER.ZOCALO: CONST.PLAN.DO_FGS,
                    "hyperion_parameters": dummy_params.json(),
                }
            )
            def inner_plan():
                yield from fake_fgs_plan()
                yield from bps.trigger_and_read(
                    [zocalo_device], name=ZOCALO_READING_PLAN_NAME
                )

            yield from inner_plan()

        RE(
            ispyb_activation_wrapper(
                trigger_zocalo_after_fast_grid_scan(), dummy_params
            )
        )
        centre = await zocalo_device.centres_of_mass.get_value()
        if centre.size == 0:
            centre = fallback
        else:
            centre = centre[0]

        return ispyb_callback, ispyb_callback.emit_cb, centre

    return inner


@pytest.mark.asyncio
@pytest.mark.s03
async def test_given_a_result_with_no_diffraction_when_zocalo_called_then_move_to_fallback(
    run_zocalo_with_dev_ispyb, zocalo_env
):
    fallback = np.array([1, 2, 3])
    _, _, centre = await run_zocalo_with_dev_ispyb("NO_DIFF", fallback)
    assert np.allclose(centre, fallback)


@pytest.mark.asyncio
@pytest.mark.s03
async def test_given_a_result_with_no_diffraction_ispyb_comment_updated(
    run_zocalo_with_dev_ispyb, zocalo_env, fetch_comment
):
    ispyb, zc, _ = await run_zocalo_with_dev_ispyb("NO_DIFF")

    comment = fetch_comment(ispyb.ispyb_ids.data_collection_ids[0])
    assert "Zocalo found no crystals in this gridscan." in comment


@pytest.mark.asyncio
@pytest.mark.s03
async def test_zocalo_adds_nonzero_comment_time(
    run_zocalo_with_dev_ispyb, zocalo_env, fetch_comment
):
    ispyb, zc, _ = await run_zocalo_with_dev_ispyb()

    comment = fetch_comment(ispyb.ispyb_ids.data_collection_ids[0])
    match = re.match(r"Zocalo processing took (\d+\.\d+) s", comment)
    assert match
    time_s = float(match.group(1))
    assert time_s > 0
    assert time_s < 180


@pytest.mark.asyncio
@pytest.mark.s03
async def test_given_a_single_crystal_result_ispyb_comment_updated(
    run_zocalo_with_dev_ispyb, zocalo_env, fetch_comment
):
    ispyb, zc, _ = await run_zocalo_with_dev_ispyb()
    comment = fetch_comment(ispyb.ispyb_ids.data_collection_ids[0])
    assert "Crystal 1" in comment
    assert "Strength" in comment
    assert "Size (grid boxes)" in comment


@pytest.mark.asyncio
@pytest.mark.s03
async def test_given_a_result_with_multiple_crystals_ispyb_comment_updated(
    run_zocalo_with_dev_ispyb, zocalo_env, fetch_comment
):
    ispyb, zc, _ = await run_zocalo_with_dev_ispyb("MULTI_X")

    comment = fetch_comment(ispyb.ispyb_ids.data_collection_ids[0])
    assert "Crystal 1" and "Crystal 2" in comment
    assert "Strength" in comment
    assert "Position (grid boxes)" in comment
