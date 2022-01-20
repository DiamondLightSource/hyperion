import pytest
from mockito import when, mock

from ophyd.sim import make_fake_device
from src.artemis.devices.eiger_odin import EigerOdin


@pytest.fixture
def fake_odin():
    FakeOdin = make_fake_device(EigerOdin)
    fake_odin: EigerOdin = FakeOdin(name='test')

    return fake_odin


@pytest.mark.parametrize(
    "is_initialised, frames_dropped, frames_timed_out, expected_state",
    [
        (True, False, False, True),
        (False, True, True, False),
        (False, False, False, False),
        (True, True, True, False)
    ]
)
def test_check_odin_state(fake_odin, is_initialised: bool, frames_dropped: bool, frames_timed_out: bool, expected_state: bool):
    when(fake_odin).check_odin_initialised().thenReturn([is_initialised, ""])
    when(fake_odin.nodes).check_frames_dropped().thenReturn([frames_dropped, ""])
    when(fake_odin.nodes).check_frames_timed_out().thenReturn([frames_timed_out, ""])

    if is_initialised:
        assert fake_odin.check_odin_state() == expected_state
    else:
        with pytest.raises(Exception):
            fake_odin.check_odin_state()
