from time import time

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import numpy as np
import pytest
import pytest_asyncio
from bluesky.run_engine import RunEngine
from dodal.devices.zocalo import (
    ZOCALO_READING_PLAN_NAME,
    ZocaloResults,
)

from hyperion.external_interaction.callbacks.xray_centre.callback_collection import (
    XrayCentreCallbackCollection,
)
from hyperion.external_interaction.ispyb.ispyb_store import IspybIds
from hyperion.parameters.constants import GRIDSCAN_OUTER_PLAN
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)

from .conftest import (
    TEST_RESULT_LARGE,
)

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


@pytest.mark.s03
@pytest.mark.asyncio
async def test_when_running_start_stop_then_get_expected_returned_results(
    dummy_params, zocalo_env, zocalo_device: ZocaloResults, RE: RunEngine
):
    start_doc = {
        "subplan_name": GRIDSCAN_OUTER_PLAN,
        "hyperion_internal_parameters": dummy_params.json(),
    }
    zc = XrayCentreCallbackCollection.setup().zocalo_handler
    zc.activity_gated_start(start_doc)
    dcids = (1, 2)
    zc.ispyb.ispyb_ids = IspybIds(
        data_collection_ids=dcids, data_collection_group_id=4, grid_ids=(0,)
    )
    for dcid in dcids:
        zc.zocalo_interactor.run_start(dcid)
    for dcid in dcids:
        zc.zocalo_interactor.run_end(dcid)
    RE(bps.trigger(zocalo_device, wait=True))
    result = await zocalo_device.read()
    assert result["zocalo-results"]["value"][0] == TEST_RESULT_LARGE[0]


@pytest.fixture
def run_zocalo_with_dev_ispyb(
    dummy_params: GridscanInternalParameters,
    dummy_ispyb_3d,
    RE: RunEngine,
    zocalo_device: ZocaloResults,
):
    async def inner(sample_name="", fallback=np.array([0, 0, 0])):
        dummy_params.hyperion_params.detector_params.prefix = sample_name
        cbs = XrayCentreCallbackCollection.setup()
        zc = cbs.zocalo_handler
        zc.active = True
        ispyb = cbs.ispyb_handler
        ispyb.ispyb_config = dummy_ispyb_3d.ISPYB_CONFIG_PATH
        ispyb.active = True

        RE.subscribe(zc)
        RE.subscribe(ispyb)

        @bpp.set_run_key_decorator("testing123")
        @bpp.run_decorator()
        def plan():
            @bpp.set_run_key_decorator("testing124")
            @bpp.run_decorator(
                md={
                    "subplan_name": GRIDSCAN_OUTER_PLAN,
                    "hyperion_internal_parameters": dummy_params.json(),
                }
            )
            def inner_plan():
                yield from bps.sleep(0)
                zc.ispyb.ispyb_ids = zc.ispyb.ispyb.begin_deposition()
                assert isinstance(zc.ispyb.ispyb_ids.data_collection_ids, tuple)
                for dcid in zc.ispyb.ispyb_ids.data_collection_ids:
                    zc.zocalo_interactor.run_start(dcid)
                zc.ispyb._processing_start_time = time()
                for dcid in zc.ispyb.ispyb_ids.data_collection_ids:
                    zc.zocalo_interactor.run_end(dcid)

            yield from inner_plan()
            yield from bps.trigger_and_read(
                [zocalo_device], name=ZOCALO_READING_PLAN_NAME
            )

        RE(plan())
        centre = await zocalo_device.centres_of_mass.get_value()
        if centre.size == 0:
            centre = fallback
        else:
            centre = centre[0]

        return zc, centre

    return inner


@pytest.mark.asyncio
@pytest.mark.s03
async def test_given_a_result_with_no_diffraction_when_zocalo_called_then_move_to_fallback(
    run_zocalo_with_dev_ispyb, zocalo_env
):
    fallback = np.array([1, 2, 3])
    zc, centre = await run_zocalo_with_dev_ispyb("NO_DIFF", fallback)
    assert np.allclose(centre, fallback)


@pytest.mark.asyncio
@pytest.mark.s03
async def test_given_a_result_with_no_diffraction_ispyb_comment_updated(
    run_zocalo_with_dev_ispyb, zocalo_env, fetch_comment
):
    zc, _ = await run_zocalo_with_dev_ispyb("NO_DIFF")

    comment = fetch_comment(zc.ispyb.ispyb_ids.data_collection_ids[0])
    assert "Zocalo found no crystals in this gridscan." in comment


@pytest.mark.asyncio
@pytest.mark.s03
async def test_zocalo_adds_nonzero_comment_time(
    run_zocalo_with_dev_ispyb, zocalo_env, fetch_comment
):
    zc, _ = await run_zocalo_with_dev_ispyb()

    comment = fetch_comment(zc.ispyb.ispyb_ids.data_collection_ids[0])
    assert comment[156:178] == "Zocalo processing took"
    assert float(comment[179:184]) > 0
    assert float(comment[179:184]) < 180


@pytest.mark.asyncio
@pytest.mark.s03
async def test_given_a_single_crystal_result_ispyb_comment_updated(
    run_zocalo_with_dev_ispyb, zocalo_env, fetch_comment
):
    zc, _ = await run_zocalo_with_dev_ispyb()
    comment = fetch_comment(zc.ispyb.ispyb_ids.data_collection_ids[0])
    assert "Crystal 1" in comment
    assert "Strength" in comment
    assert "Size (grid boxes)" in comment


@pytest.mark.asyncio
@pytest.mark.s03
async def test_given_a_result_with_multiple_crystals_ispyb_comment_updated(
    run_zocalo_with_dev_ispyb, zocalo_env, fetch_comment
):
    zc, _ = await run_zocalo_with_dev_ispyb("MULTI_X")

    comment = fetch_comment(zc.ispyb.ispyb_ids.data_collection_ids[0])
    assert "Crystal 1" and "Crystal 2" in comment
    assert "Strength" in comment
    assert "Position (grid boxes)" in comment
