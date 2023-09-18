from unittest.mock import MagicMock

import pytest
from bluesky import RunEngine
from bluesky import plan_stubs as bps
from bluesky.run_engine import RunEngine
from dodal.beamlines import i03

from hyperion.device_setup_plans.utils import (
    start_preparing_data_collection_then_do_plan,
)


def test_given_plan_raises_when_exception_raised_then_eiger_disarmed_and_correct_exception_returned():
    class TestException(Exception):
        pass

    def my_plan():
        yield from bps.null()
        raise TestException()

    eiger = i03.eiger(fake_with_ophyd_sim=True)
    eiger.detector_params = MagicMock()
    eiger.async_stage = MagicMock()
    eiger.disarm_detector = MagicMock()

    RE = RunEngine()

    with pytest.raises(TestException):
        RE(start_preparing_data_collection_then_do_plan(eiger, my_plan()))

    # Check detector was armed
    eiger.async_stage.assert_called_once()

    eiger.disarm_detector.assert_called_once()
