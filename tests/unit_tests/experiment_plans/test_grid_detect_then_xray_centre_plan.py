from typing import Dict, Generator
from unittest.mock import ANY, MagicMock, patch

import bluesky.plan_stubs as bps
import pytest
from bluesky.run_engine import RunEngine
from dodal.beamlines import i03
from dodal.devices.backlight import BacklightPosition
from dodal.devices.eiger import EigerDetector
from dodal.devices.oav.oav_detector import OAVConfigParams
from dodal.devices.oav.oav_parameters import OAVParameters
from dodal.devices.smargon import Smargon

from hyperion.experiment_plans.grid_detect_then_xray_centre_plan import (
    GridDetectThenXRayCentreComposite,
    OavGridDetectionComposite,
    detect_grid_and_do_gridscan,
    grid_detect_then_xray_centre,
)
from hyperion.parameters.constants import CONST
from hyperion.parameters.gridscan import GridScanWithEdgeDetect, ThreeDGridScan


def _fake_grid_detection(
    devices: OavGridDetectionComposite,
    parameters: OAVParameters,
    snapshot_template: str,
    snapshot_dir: str,
    grid_width_microns: float = 0,
    box_size_um: float = 0.0,
):
    oav = i03.oav(fake_with_ophyd_sim=True)
    oav.grid_snapshot.box_width.put(635.00986)
    # first grid detection: x * y
    oav.grid_snapshot.num_boxes_x.put(10)
    oav.grid_snapshot.num_boxes_y.put(4)
    yield from bps.create(CONST.DESCRIPTORS.OAV_GRID_SNAPSHOT_TRIGGERED)
    yield from bps.read(oav.grid_snapshot)
    yield from bps.read(devices.smargon)
    yield from bps.save()

    # second grid detection: x * z, so num_boxes_y refers to smargon z
    oav.grid_snapshot.num_boxes_x.put(10)
    oav.grid_snapshot.num_boxes_y.put(1)
    yield from bps.create(CONST.DESCRIPTORS.OAV_GRID_SNAPSHOT_TRIGGERED)
    yield from bps.read(oav.grid_snapshot)
    yield from bps.read(devices.smargon)
    yield from bps.save()


@pytest.fixture
def grid_detect_devices(aperture_scatterguard, backlight, detector_motion, smargon):
    return GridDetectThenXRayCentreComposite(
        aperture_scatterguard=aperture_scatterguard,
        attenuator=MagicMock(),
        backlight=backlight,
        detector_motion=detector_motion,
        eiger=MagicMock(),
        zebra_fast_grid_scan=MagicMock(),
        flux=MagicMock(),
        oav=MagicMock(),
        pin_tip_detection=MagicMock(),
        smargon=smargon,
        synchrotron=MagicMock(),
        s4_slit_gaps=MagicMock(),
        undulator=MagicMock(),
        xbpm_feedback=MagicMock(),
        zebra=MagicMock(),
        zocalo=MagicMock(),
        panda=MagicMock(),
        panda_fast_grid_scan=MagicMock(),
        dcm=MagicMock(),
        robot=MagicMock(),
    )


def test_full_grid_scan(test_fgs_params, test_config_files):
    devices = MagicMock()
    plan = grid_detect_then_xray_centre(
        devices, test_fgs_params, test_config_files["oav_config_json"]
    )
    assert isinstance(plan, Generator)


@patch(
    "hyperion.experiment_plans.grid_detect_then_xray_centre_plan.grid_detection_plan",
    autospec=True,
)
@patch(
    "hyperion.experiment_plans.grid_detect_then_xray_centre_plan.flyscan_xray_centre",
    autospec=True,
)
async def test_detect_grid_and_do_gridscan(
    mock_flyscan_xray_centre_plan: MagicMock,
    mock_grid_detection_plan: MagicMock,
    grid_detect_devices: GridDetectThenXRayCentreComposite,
    RE: RunEngine,
    smargon: Smargon,
    test_full_grid_scan_params: GridScanWithEdgeDetect,
    test_config_files: Dict,
):
    mock_grid_detection_plan.side_effect = _fake_grid_detection
    grid_detect_devices.oav.parameters = OAVConfigParams(
        test_config_files["zoom_params_file"], test_config_files["display_config"]
    )
    grid_detect_devices.oav.parameters.micronsPerXPixel = 0.806
    grid_detect_devices.oav.parameters.micronsPerYPixel = 0.806
    grid_detect_devices.oav.parameters.beam_centre_i = 549
    grid_detect_devices.oav.parameters.beam_centre_j = 347
    assert grid_detect_devices.aperture_scatterguard.aperture_positions is not None

    with patch.object(
        grid_detect_devices.aperture_scatterguard, "set", MagicMock()
    ) as mock_aperture_scatterguard:
        RE(
            detect_grid_and_do_gridscan(
                grid_detect_devices,
                parameters=test_full_grid_scan_params,
                oav_params=OAVParameters(
                    "xrayCentring", test_config_files["oav_config_json"]
                ),
            )
        )
        # Verify we called the grid detection plan
        mock_grid_detection_plan.assert_called_once()

        # Check backlight was moved OUT
        assert (
            await grid_detect_devices.backlight.position.get_value()
            == BacklightPosition.OUT
        )

        # Check aperture was changed to SMALL
        mock_aperture_scatterguard.assert_called_once_with(
            grid_detect_devices.aperture_scatterguard.aperture_positions.SMALL
        )

        # Check we called out to underlying fast grid scan plan
        mock_flyscan_xray_centre_plan.assert_called_once_with(ANY, ANY)


@patch(
    "hyperion.experiment_plans.grid_detect_then_xray_centre_plan.grid_detection_plan",
    autospec=True,
)
@patch(
    "hyperion.experiment_plans.grid_detect_then_xray_centre_plan.flyscan_xray_centre",
    autospec=True,
)
def test_when_full_grid_scan_run_then_parameters_sent_to_fgs_as_expected(
    mock_flyscan_xray_centre_plan: MagicMock,
    mock_grid_detection_plan: MagicMock,
    eiger: EigerDetector,
    grid_detect_devices: GridDetectThenXRayCentreComposite,
    RE: RunEngine,
    test_full_grid_scan_params: GridScanWithEdgeDetect,
    test_config_files: Dict,
    smargon: Smargon,
):
    oav_params = OAVParameters("xrayCentring", test_config_files["oav_config_json"])

    mock_grid_detection_plan.side_effect = _fake_grid_detection

    grid_detect_devices.oav.parameters = OAVConfigParams(
        test_config_files["zoom_params_file"], test_config_files["display_config"]
    )
    grid_detect_devices.oav.parameters.micronsPerXPixel = 0.806
    grid_detect_devices.oav.parameters.micronsPerYPixel = 0.806
    grid_detect_devices.oav.parameters.beam_centre_i = 549
    grid_detect_devices.oav.parameters.beam_centre_j = 347

    with patch.object(eiger.do_arm, "set", MagicMock()), patch.object(
        grid_detect_devices.aperture_scatterguard, "set", MagicMock()
    ):
        RE(
            detect_grid_and_do_gridscan(
                grid_detect_devices,
                parameters=test_full_grid_scan_params,
                oav_params=oav_params,
            )
        )

        params: ThreeDGridScan = mock_flyscan_xray_centre_plan.call_args[0][1]

        assert params.detector_params.num_triggers == 50

        assert params.FGS_params.x_axis.full_steps == 10
        assert params.FGS_params.y_axis.end == pytest.approx(1.511, 0.001)

        # Parameters can be serialized
        params.json()
