from bluesky.run_engine import RunEngine
import pytest
from artemis.experiment_plans.oav_grid_detection_plan import grid_detection_plan
from unittest.mock import patch
from dodal import i03
from artemis.parameters.internal_parameters.plan_specific.fgs_internal_params import (
    FGSInternalParameters,
)
from artemis.parameters.external_parameters import from_file
from dodal.devices.fast_grid_scan import GridScanParams
from dodal.devices.oav.oav_parameters import OAVParameters


@pytest.fixture
def RE():
    return RunEngine({})


def fake_create_devices():
    i03.oav(fake_with_ophyd_sim=True).wait_for_connection()
    i03.smargon(fake_with_ophyd_sim=True).wait_for_connection()
    i03.backlight(fake_with_ophyd_sim=True).wait_for_connection()


@patch(
    "artemis.experiment_plans.oav_grid_detection_plan.create_devices",
    fake_create_devices,
)
def test_grid_detection_plan(RE):
    params = OAVParameters()
    gridscan_params = GridScanParams()
    RE(
        grid_detection_plan(
            parameters=params,
            out_parameters=gridscan_params,
            filenames={
                "snapshot_dir": "tmp",
                "snap_1_filename": "1.jpg",
                "snap_2_filename": "2.jpg",
            },
        )
    )
