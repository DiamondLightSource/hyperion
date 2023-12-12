import bluesky.plan_stubs as bps
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
from hyperion.external_interaction.ispyb.store_in_ispyb import IspybIds
from hyperion.parameters.constants import GRIDSCAN_OUTER_PLAN
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)

from .conftest import (
    TEST_RESULT_LARGE,
)


@pytest_asyncio.fixture
async def zocalo_device():
    zd = ZocaloResults()
    zd.timeout_s = 5
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
    assert result["zocalo_results-results"]["value"][0] == TEST_RESULT_LARGE[0]


@pytest.fixture
def run_zocalo_with_dev_ispyb(
    dummy_params: GridscanInternalParameters,
    dummy_ispyb_3d,
    RE: RunEngine,
    zocalo_device: ZocaloResults,
):
    async def inner(sample_name="", fallback=np.array([0, 0, 0])):
        dummy_params.hyperion_params.detector_params.prefix = sample_name
        start_doc = {
            "subplan_name": GRIDSCAN_OUTER_PLAN,
            "hyperion_internal_parameters": dummy_params.json(),
            "uid": "test",
        }
        cbs = XrayCentreCallbackCollection.setup()
        zc = cbs.zocalo_handler
        zc.active = True
        ispyb = cbs.ispyb_handler
        ispyb.active = True
        ispyb.activity_gated_start(start_doc)
        zc.activity_gated_start(start_doc)
        zc.ispyb.ispyb.ISPYB_CONFIG_PATH = dummy_ispyb_3d.ISPYB_CONFIG_PATH
        zc.ispyb.ispyb_ids = zc.ispyb.ispyb.begin_deposition()
        assert isinstance(zc.ispyb.ispyb_ids.data_collection_ids, tuple)
        for dcid in zc.ispyb.ispyb_ids.data_collection_ids:
            zc.zocalo_interactor.run_start(dcid)
        ispyb.activity_gated_stop({})
        zc.activity_gated_stop({})
        RE.subscribe(ispyb)

        def plan():
            yield from bps.open_run()
            yield from bps.trigger_and_read(
                [zocalo_device], name=ZOCALO_READING_PLAN_NAME
            )
            yield from bps.close_run()

        RE(plan())
        ispyb.activity_gated_stop({"run_start": "test"})
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
