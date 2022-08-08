from pathlib import Path
from unittest.mock import MagicMock, call, patch

import PIL
import pytest
from ophyd.sim import make_fake_device
from requests import HTTPError, Response

from src.artemis.devices.oav import OAV


@pytest.fixture
def fake_oav() -> OAV:
    FakeOAV = make_fake_device(OAV)
    fake_oav: OAV = FakeOAV(name="test")

    fake_oav.snapshot.url.sim_put("http://test.url")
    fake_oav.snapshot.filename.put("test filename")
    fake_oav.snapshot.directory.put("test directory")
    fake_oav.snapshot.top_left_x_signal.put(100)
    fake_oav.snapshot.top_left_y_signal.put(100)
    fake_oav.snapshot.box_width_signal.put(50)
    fake_oav.snapshot.num_boxes_x_signal.put(15)
    fake_oav.snapshot.num_boxes_y_signal.put(10)
    return fake_oav


@patch("requests.get")
def test_snapshot_trigger_handles_request_with_bad_status_code_correctly(
    mock_get, fake_oav: OAV
):
    response = Response()
    response.status_code = 404
    mock_get.return_value = response

    st = fake_oav.snapshot.trigger()
    with pytest.raises(HTTPError):
        st.wait()


@patch("requests.get")
@patch("src.artemis.devices.oav.snapshot.Image")
def test_snapshot_trigger_loads_correct_url(mock_image, mock_get: MagicMock, fake_oav):
    st = fake_oav.snapshot.trigger()
    st.wait()
    mock_get.assert_called_once_with("http://test.url", stream=True)


@patch("requests.get")
@patch("src.artemis.devices.oav.snapshot.Image.open")
def test_snapshot_trigger_saves_to_correct_file(
    mock_open: MagicMock, mock_get, fake_oav
):
    image = PIL.Image.open("test")
    mock_save = MagicMock()
    image.save = mock_save
    mock_open.return_value = image
    st = fake_oav.snapshot.trigger()
    st.wait()
    expected_calls_to_save = [
        call(Path(f"test directory/test filename{addition}.png"))
        for addition in ["", "_outer_overlay", "_grid_overlay"]
    ]
    calls_to_save = mock_save.mock_calls
    assert calls_to_save == expected_calls_to_save


@patch("requests.get")
@patch("src.artemis.devices.oav.snapshot.Image.open")
@patch("src.artemis.devices.oav.grid_overlay.add_grid_overlay_to_image")
@patch("src.artemis.devices.oav.grid_overlay.add_grid_border_overlay_to_image")
def test_correct_grid_drawn_on_image(
    mock_border_overlay: MagicMock,
    mock_grid_overlay: MagicMock,
    mock_open: MagicMock,
    mock_get: MagicMock,
    fake_oav: OAV,
):
    st = fake_oav.snapshot.trigger()
    st.wait()
    expected_border_calls = [call(mock_open.return_value, 100, 100, 50, 15, 10)]
    expected_grid_calls = [call(mock_open.return_value, 100, 100, 50, 15, 10)]
    actual_border_calls = mock_border_overlay.mock_calls
    actual_grid_calls = mock_grid_overlay.mock_calls
    assert actual_border_calls == expected_border_calls
    assert actual_grid_calls == expected_grid_calls
