import pytest
from mockito import mock, when, verify, ANY

from ophyd.sim import make_fake_device
from src.artemis.devices.eiger import EigerDetector, DetectorParams
from src.artemis.devices.det_dim_constants import DetectorSizeConstants, DetectorSize


TEST_EIGER_STRING = "EIGER2_X_4M"
TEST_EIGER_DIMENSION_X = 155.1
TEST_EIGER_DIMENSION_Y = 162.15
TEST_EIGER_DIMENSION = DetectorSize(TEST_EIGER_DIMENSION_X, TEST_EIGER_DIMENSION_Y)
TEST_PIXELS_X_EIGER = 2068
TEST_PIXELS_Y_EIGER = 2162
TEST_PIXELS_EIGER = DetectorSize(TEST_PIXELS_X_EIGER, TEST_PIXELS_Y_EIGER)
TEST_DETECTOR_SIZE_CONSTANTS = DetectorSizeConstants(TEST_EIGER_STRING, TEST_EIGER_DIMENSION, TEST_PIXELS_EIGER,
                                                     TEST_EIGER_DIMENSION, TEST_PIXELS_EIGER)


@pytest.fixture
def fake_eiger():
    FakeEigerDetector = make_fake_device(EigerDetector)
    fake_eiger: EigerDetector = FakeEigerDetector(name='test')

    return fake_eiger


@pytest.mark.parametrize(
    "current_energy, request_energy, is_energy_change",
    [
        (100.0, 100.0, False),
        (100.0, 200.0, True),
        (100.0, 50.0, True),
        (100.0, 100.09, False),
        (100.0, 99.91, False)
    ]
)
def test_detector_threshold(fake_eiger, current_energy: float, request_energy: float, is_energy_change: bool):

    when(fake_eiger.cam.photon_energy).get().thenReturn(current_energy)
    when(fake_eiger.cam.photon_energy).put(ANY).thenReturn(None)

    assert fake_eiger.set_detector_threshold(request_energy) == is_energy_change

    if is_energy_change:
        verify(fake_eiger.cam.photon_energy, times=1).put(request_energy)
    else:
        verify(fake_eiger.cam.photon_energy, times=0).put(ANY)


@pytest.mark.parametrize(
    "detector_params, detector_size_constants, beam_xy_converter, expected_error_number",
    [
        (mock(), mock(), mock(), 0),
        (None, mock(), mock(), 1),
        (mock(), None, mock(), 1),
        (None, None, mock(), 1),
        (None, None, None, 1),
        (mock(), None, None, 2)
    ]
)
def test_check_detector_variables(fake_eiger, detector_params, detector_size_constants, beam_xy_converter, expected_error_number):
    fake_eiger.detector_params = detector_params

    if detector_params is not None:
        fake_eiger.detector_params.beam_xy_converter = beam_xy_converter
        fake_eiger.detector_params.detector_size_constants = detector_size_constants

    if expected_error_number != 0:
        with pytest.raises(Exception) as e:
            fake_eiger.check_detector_variables_set()
        number_of_errors = str(e.value).count('\n') + 1

        assert number_of_errors == expected_error_number
    else:
        try:
            fake_eiger.check_detector_variables_set()
        except Exception as e:
            assert False, f"exception was raised {e}"
