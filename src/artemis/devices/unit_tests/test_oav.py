from unittest.mock import MagicMock, patch

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
@patch("src.artemis.devices.oav.Image")
def test_snapshot_trigger_loads_correct_url(mock_image, mock_get: MagicMock, fake_oav):
    st = fake_oav.snapshot.trigger()
    st.wait()
    mock_get.assert_called_once_with("http://test.url", stream=True)


@patch("requests.get")
@patch("src.artemis.devices.oav.Image.open")
def test_snapshot_trigger_saves_to_correct_file(
    mock_open: MagicMock, mock_get, fake_oav
):
    image = PIL.Image.open("test")
    mock_save = MagicMock()
    image.save = mock_save
    mock_open.return_value = image
    st = fake_oav.snapshot.trigger()
    st.wait()
    mock_save.assert_called_once_with("test filename")
