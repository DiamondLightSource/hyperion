from unittest.mock import DEFAULT, AsyncMock, MagicMock, patch

import bluesky.preprocessors as bpp
import numpy as np
import pytest
from bluesky.run_engine import RunEngine
from bluesky.utils import Msg
from dodal.beamlines import i03
from dodal.devices.backlight import Backlight
from dodal.devices.fast_grid_scan import GridAxis
from dodal.devices.oav.oav_detector import OAVConfigParams
from dodal.devices.oav.oav_parameters import OAVParameters
from dodal.devices.oav.pin_image_recognition import PinTipDetection
from dodal.devices.oav.pin_image_recognition.utils import NONE_VALUE, SampleLocation
from dodal.devices.smargon import Smargon

from hyperion.exceptions import WarningException
from hyperion.experiment_plans.oav_grid_detection_plan import (
    OavGridDetectionComposite,
    get_min_and_max_y_of_pin,
    grid_detection_plan,
)
from hyperion.external_interaction.callbacks.grid_detection_callback import (
    GridDetectionCallback,
)
from hyperion.external_interaction.callbacks.oav_snapshot_callback import (
    OavSnapshotCallback,
)
from hyperion.external_interaction.callbacks.xray_centre.ispyb_callback import (
    GridscanISPyBCallback,
    ispyb_activation_wrapper,
)

from ...conftest import RunEngineSimulator
from .conftest import assert_event


@pytest.fixture
def fake_devices(RE, smargon: Smargon, backlight: Backlight, test_config_files):
    oav = i03.oav(wait_for_connection=False, fake_with_ophyd_sim=True)

    oav.parameters = OAVConfigParams(
        test_config_files["zoom_params_file"], test_config_files["display_config"]
    )
    oav.parameters.update_on_zoom = MagicMock()
    oav.parameters.load_microns_per_pixel = MagicMock()
    oav.parameters.micronsPerXPixel = 1.58
    oav.parameters.micronsPerYPixel = 1.58
    oav.parameters.beam_centre_i = 517
    oav.parameters.beam_centre_j = 350

    oav.wait_for_connection()

    pin_tip_detection = i03.pin_tip_detection(fake_with_ophyd_sim=True)
    pin_tip_detection._get_tip_and_edge_data = AsyncMock(
        return_value=SampleLocation(
            8,
            5,
            np.array([0, 0, 0, 0, 0, 0, 0, 0, 5, 5, 4, 4, 3, 3, 2, 2, 3, 3, 4, 4]),
            np.array([0, 0, 0, 0, 0, 0, 0, 0, 5, 5, 6, 6, 7, 7, 8, 8, 7, 7, 6, 6]),
        )
    )

    oav.zoom_controller.zrst.set("1.0x")
    oav.zoom_controller.onst.set("2.0x")
    oav.zoom_controller.twst.set("3.0x")
    oav.zoom_controller.thst.set("5.0x")
    oav.zoom_controller.frst.set("7.0x")
    oav.zoom_controller.fvst.set("9.0x")

    with patch("dodal.devices.areadetector.plugins.MJPG.requests"), patch(
        "dodal.devices.areadetector.plugins.MJPG.Image"
    ) as mock_image_class:
        mock_image = MagicMock()
        mock_image_class.open.return_value.__enter__.return_value = mock_image

        composite = OavGridDetectionComposite(
            backlight=backlight,
            oav=oav,
            smargon=smargon,
            pin_tip_detection=pin_tip_detection,
        )

        yield composite, mock_image


@patch("dodal.beamlines.beamline_utils.active_device_is_same_type", lambda a, b: True)
@patch("bluesky.plan_stubs.sleep", new=MagicMock())
def test_grid_detection_plan_runs_and_triggers_snapshots(
    RE: RunEngine,
    test_config_files,
    fake_devices,
):
    params = OAVParameters("loopCentring", test_config_files["oav_config_json"])
    cb = OavSnapshotCallback()
    RE.subscribe(cb)
    composite, image = fake_devices

    @bpp.run_decorator()
    def decorated():
        yield from grid_detection_plan(
            composite,
            parameters=params,
            snapshot_dir="tmp",
            snapshot_template="test_{angle}",
            grid_width_microns=161.2,
        )

    RE(decorated())
    assert image.save.call_count == 6

    assert len(cb.snapshot_filenames) == 2
    assert len(cb.snapshot_filenames[0]) == 3
    assert cb.snapshot_filenames[0][0] == "tmp/test_0.png"
    assert cb.snapshot_filenames[1][2] == "tmp/test_90_grid_overlay.png"

    assert len(cb.out_upper_left) == 2
    assert len(cb.out_upper_left[0])


@patch("dodal.beamlines.beamline_utils.active_device_is_same_type", lambda a, b: True)
@patch("bluesky.plan_stubs.sleep", new=MagicMock())
@pytest.mark.asyncio
async def test_grid_detection_plan_gives_warningerror_if_tip_not_found(
    RE,
    test_config_files,
    fake_devices: tuple[OavGridDetectionComposite, MagicMock],
):
    composite, _ = fake_devices

    await composite.pin_tip_detection.validity_timeout._backend.put(0.01)
    composite.pin_tip_detection._get_tip_and_edge_data = AsyncMock(
        return_value=SampleLocation(
            *PinTipDetection.INVALID_POSITION,
            np.array([]),
            np.array([]),
        )
    )

    params = OAVParameters("loopCentring", test_config_files["oav_config_json"])

    with pytest.raises(WarningException) as excinfo:
        RE(
            grid_detection_plan(
                composite,
                parameters=params,
                snapshot_dir="tmp",
                snapshot_template="test_{angle}",
                grid_width_microns=161.2,
            )
        )
    assert "No pin found" in excinfo.value.args[0]


@patch("dodal.beamlines.beamline_utils.active_device_is_same_type", lambda a, b: True)
@patch("bluesky.plan_stubs.sleep", new=MagicMock())
def test_given_when_grid_detect_then_upper_left_and_start_position_as_expected(
    fake_devices,
    RE: RunEngine,
    test_config_files,
):
    params = OAVParameters("loopCentring", test_config_files["oav_config_json"])
    box_size_um = 0.2
    composite, _ = fake_devices
    composite.oav.parameters.micronsPerXPixel = 0.1
    composite.oav.parameters.micronsPerYPixel = 0.1
    composite.oav.parameters.beam_centre_i = 4
    composite.oav.parameters.beam_centre_j = 4
    box_size_y_pixels = box_size_um / composite.oav.parameters.micronsPerYPixel

    oav_cb = OavSnapshotCallback()
    grid_param_cb = GridDetectionCallback(composite.oav.parameters, 0.004, False)
    RE.subscribe(oav_cb)
    RE.subscribe(grid_param_cb)

    @bpp.run_decorator()
    def decorated():
        yield from grid_detection_plan(
            composite,
            parameters=params,
            snapshot_dir="tmp",
            snapshot_template="test_{angle}",
            grid_width_microns=161.2,
            box_size_um=0.2,
        )

    RE(decorated())

    # 8, 2 based on tip x, and lowest value in the top array
    assert oav_cb.out_upper_left[0] == [8, 2 - box_size_y_pixels / 2]
    assert oav_cb.out_upper_left[1] == [8, 2]

    gridscan_params = grid_param_cb.get_grid_parameters()

    assert gridscan_params.x_start == pytest.approx(0.0005)
    assert gridscan_params.y1_start == pytest.approx(
        -0.0001
        - (
            (box_size_y_pixels / 2) * composite.oav.parameters.micronsPerYPixel * 1e-3
        )  # microns to mm
    )
    assert gridscan_params.z1_start == pytest.approx(-0.0001)


@patch("dodal.beamlines.beamline_utils.active_device_is_same_type", lambda a, b: True)
@patch("bluesky.plan_stubs.sleep", new=MagicMock())
@patch(
    "hyperion.experiment_plans.oav_grid_detection_plan.pre_centring_setup_oav",
    new=MagicMock(),
)
def test_when_grid_detection_plan_run_twice_then_values_do_not_persist_in_callback(
    fake_devices,
    RE: RunEngine,
    test_config_files,
):
    params = OAVParameters("loopCentring", test_config_files["oav_config_json"])

    composite, _ = fake_devices

    for _ in range(2):
        cb = OavSnapshotCallback()
        RE.subscribe(cb)

        @bpp.run_decorator()
        def decorated():
            yield from grid_detection_plan(
                composite,
                parameters=params,
                snapshot_dir="tmp",
                snapshot_template="test_{angle}",
                grid_width_microns=161.2,
            )

        RE(decorated())
    assert len(cb.snapshot_filenames) == 2
    assert len(cb.out_upper_left) == 2


@patch("dodal.beamlines.beamline_utils.active_device_is_same_type", lambda a, b: True)
@patch("bluesky.plan_stubs.sleep", new=MagicMock())
def test_when_grid_detection_plan_run_then_ispyb_callback_gets_correct_values(
    fake_devices, RE: RunEngine, test_config_files, test_fgs_params
):
    params = OAVParameters("loopCentring", test_config_files["oav_config_json"])
    composite, _ = fake_devices
    composite.oav.parameters.micronsPerYPixel = 1.25
    composite.oav.parameters.micronsPerXPixel = 1.25
    cb = GridscanISPyBCallback()
    RE.subscribe(cb)

    def decorated():
        yield from grid_detection_plan(
            composite,
            parameters=params,
            snapshot_dir="tmp",
            snapshot_template="test_{angle}",
            grid_width_microns=161.2,
        )

    with patch.multiple(cb, activity_gated_start=DEFAULT, activity_gated_event=DEFAULT):
        RE(ispyb_activation_wrapper(test_fgs_params, decorated()))

        assert_event(
            cb.activity_gated_start.mock_calls[0],
            {"activate_callbacks": ["GridscanISPyBCallback"]},
        )
        assert_event(
            cb.activity_gated_event.mock_calls[0],
            {
                "oav_snapshot_top_left_x": 8,
                "oav_snapshot_top_left_y": -6,
                "oav_snapshot_num_boxes_x": 8,
                "oav_snapshot_num_boxes_y": 2,
                "oav_snapshot_box_width": 16,
            },
        )


@patch("dodal.beamlines.beamline_utils.active_device_is_same_type", lambda a, b: True)
@patch("bluesky.plan_stubs.sleep", new=MagicMock())
def test_when_grid_detection_plan_run_then_grid_detection_callback_gets_correct_values(
    fake_devices, RE: RunEngine, test_config_files, test_fgs_params
):
    params = OAVParameters("loopCentring", test_config_files["oav_config_json"])
    composite, _ = fake_devices
    box_size_um = 20
    cb = GridDetectionCallback(composite.oav.parameters, 0.5, True)
    RE.subscribe(cb)

    def decorated():
        yield from grid_detection_plan(
            composite,
            parameters=params,
            snapshot_dir="tmp",
            snapshot_template="test_{angle}",
            grid_width_microns=161.2,
        )

    RE(ispyb_activation_wrapper(test_fgs_params, decorated()))

    my_grid_params = cb.get_grid_parameters()

    test_x_grid_axis = GridAxis(
        start=my_grid_params.x_start,
        step_size=my_grid_params.x_step_size,
        full_steps=my_grid_params.x_steps,
    )

    test_y_grid_axis = GridAxis(
        start=my_grid_params.y1_start,
        step_size=my_grid_params.y_step_size,
        full_steps=my_grid_params.y_steps,
    )

    test_z_grid_axis = GridAxis(
        start=my_grid_params.z2_start,
        step_size=my_grid_params.z_step_size,
        full_steps=my_grid_params.z_steps,
    )

    assert my_grid_params.x_start == pytest.approx(-0.7942199999999999)
    assert my_grid_params.y1_start == pytest.approx(-0.53984 - (box_size_um * 1e-3 / 2))
    assert my_grid_params.y2_start == pytest.approx(-0.53984 - (box_size_um * 1e-3 / 2))
    assert my_grid_params.z1_start == pytest.approx(-0.53984)
    assert my_grid_params.z2_start == pytest.approx(-0.53984)
    assert my_grid_params.x_step_size == pytest.approx(0.02)
    assert my_grid_params.y_step_size == pytest.approx(0.02)
    assert my_grid_params.z_step_size == pytest.approx(0.02)
    assert my_grid_params.x_steps == pytest.approx(9)
    assert my_grid_params.y_steps == pytest.approx(2)
    assert my_grid_params.z_steps == pytest.approx(1)
    assert cb.x_step_size_mm == cb.y_step_size_mm == cb.z_step_size_mm == 0.02

    assert my_grid_params.dwell_time_ms == pytest.approx(500)

    assert my_grid_params.x_axis == test_x_grid_axis
    assert my_grid_params.y_axis == test_y_grid_axis
    assert my_grid_params.z_axis == test_z_grid_axis

    assert my_grid_params.set_stub_offsets is True


@pytest.mark.parametrize(
    "odd",
    [(True), (False)],
)
@patch("dodal.beamlines.beamline_utils.active_device_is_same_type", lambda a, b: True)
@patch("bluesky.plan_stubs.sleep", new=MagicMock())
@patch("hyperion.experiment_plans.oav_grid_detection_plan.LOGGER")
def test_when_detected_grid_has_odd_y_steps_then_add_a_y_step_and_shift_grid(
    fake_logger: MagicMock,
    fake_devices,
    test_config_files,
    odd,
):
    composite, _ = fake_devices
    sim = RunEngineSimulator()
    params = OAVParameters("loopCentring", test_config_files["oav_config_json"])
    grid_width_microns = 161.2
    box_size_um = 20
    box_size_y_pixels = box_size_um / composite.oav.parameters.micronsPerYPixel
    initial_min_y = 1

    abs_sets: dict[str, list] = {"snapshot.top_left_y": [], "snapshot.num_boxes_y": []}

    def handle_read(msg: Msg):
        if msg.obj.name == "pin_tip_detection-triggered_tip":
            return {"values": {"value": (8, 5)}}
        if msg.obj.name == "pin_tip_detection-triggered_top_edge":
            top_edge = [0] * 20
            top_edge[19] = initial_min_y
            return {"values": {"value": top_edge}}
        elif msg.obj.name == "pin_tip_detection-triggered_bottom_edge":
            bottom_edge = [0] * 20
            bottom_edge[19] = (
                10 if odd else 25
            )  # Ensure y steps comes out as even or odd
            return {"values": {"value": bottom_edge}}
        else:
            pass

    def record_set(msg: Msg):
        if hasattr(msg.obj, "dotted_name"):
            if msg.obj.dotted_name in abs_sets.keys():
                abs_sets[msg.obj.dotted_name].append(msg.args[0])

    sim.add_handler(
        "set",
        None,
        record_set,
    )

    sim.add_handler(
        "read",
        None,
        handle_read,
    )

    sim.simulate_plan(
        grid_detection_plan(
            composite,
            parameters=params,
            snapshot_dir="tmp",
            snapshot_template="test_{angle}",
            grid_width_microns=grid_width_microns,
        )
    )

    expected_min_y = initial_min_y - box_size_y_pixels / 2 if odd else initial_min_y
    expected_y_steps = 2

    if odd:
        fake_logger.debug.assert_called_once_with(
            f"Forcing number of rows in first grid to be even: Adding an extra row onto bottom of first grid and shifting grid upwards by {box_size_y_pixels/2}"
        )
    else:
        fake_logger.debug.assert_not_called()

    assert abs_sets["snapshot.top_left_y"][0] == expected_min_y
    assert abs_sets["snapshot.num_boxes_y"][0] == expected_y_steps


@pytest.mark.parametrize(
    "top, bottom, expected_min, expected_max",
    [
        (np.array([1, 2, 5]), np.array([8, 9, 40]), 1, 40),
        (np.array([9, 6, 10]), np.array([152, 985, 72]), 6, 985),
        (np.array([5, 1]), np.array([999, 1056, 896, 10]), 1, 1056),
    ],
)
def test_given_array_with_valid_top_and_bottom_then_min_and_max_as_expected(
    top, bottom, expected_min, expected_max
):
    min_y, max_y = get_min_and_max_y_of_pin(top, bottom, 100)
    assert min_y == expected_min
    assert max_y == expected_max


@pytest.mark.parametrize(
    "top, bottom, expected_min, expected_max",
    [
        (np.array([1, 2, NONE_VALUE]), np.array([8, 9, 40]), 1, 40),
        (np.array([6, NONE_VALUE, 10]), np.array([152, 985, NONE_VALUE]), 6, 985),
        (np.array([1, 5]), np.array([999, 1056, NONE_VALUE, 10]), 1, 1056),
    ],
)
def test_given_array_with_some_invalid_top_and_bottom_sections_then_min_and_max_as_expected(
    top, bottom, expected_min, expected_max
):
    min_y, max_y = get_min_and_max_y_of_pin(top, bottom, 100)
    assert min_y == expected_min
    assert max_y == expected_max


@pytest.mark.parametrize(
    "top, bottom, expected_min, expected_max",
    [
        (np.array([NONE_VALUE, 0, NONE_VALUE]), np.array([100, NONE_VALUE]), 0, 100),
        (np.array([NONE_VALUE, NONE_VALUE]), np.array([100, NONE_VALUE]), 0, 100),
        (np.array([0, NONE_VALUE]), np.array([NONE_VALUE]), 0, 100),
    ],
)
def test_given_array_with_all_invalid_top_and_bottom_sections_then_min_and_max_is_full_image(
    top, bottom, expected_min, expected_max
):
    min_y, max_y = get_min_and_max_y_of_pin(top, bottom, 100)
    assert min_y == expected_min
    assert max_y == expected_max
