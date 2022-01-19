from src.artemis.devices.eiger import EigerDetector, DetectorParams
from src.artemis.devices.det_dim_constants import EIGER2_X_16M_SIZE
from src.artemis.devices.det_dist_to_beam_converter import (
    DetectorDistanceToBeamXYConverter,
)

import pytest
import os
from epics import caput


@pytest.fixture()
def eiger():
    eiger = EigerDetector(name="eiger", prefix="BL03S-EA-EIGER-01:")
    eiger.detector_size_constants = EIGER2_X_16M_SIZE
    eiger.use_roi_mode = True
    eiger.detector_params = DetectorParams(
        100, 0.1, "001", "/tmp/", "file.h5", 100.0, 0, 0.1, 10
    )
    eiger.beam_xy_converter = DetectorDistanceToBeamXYConverter(
        os.path.join(
            os.path.dirname(__file__), "..", "det_dist_to_beam_XY_converter.txt"
        )
    )

    # S03 currently does not have logic for odin meta to be initialised
    caput(eiger.odin.meta.initialised.pvname, 1)

    # S03 currently does not have StaleParameters_RBV
    eiger.wait_for_stale_parameters = lambda: None

    yield eiger


@pytest.mark.s03
def test_can_stage_and_unstage_eiger(eiger: EigerDetector):
    eiger.stage()
    assert eiger.cam.acquire.get() == 1
    # S03 filewriters stay in error
    eiger.odin.check_odin_initialised = lambda: (True, "")
    eiger.unstage()
    assert eiger.cam.acquire.get() == 0
