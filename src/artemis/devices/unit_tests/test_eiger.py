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


def test_get_beam_position(fake_eiger):
    fake_eiger.detector_size_constants = TEST_DETECTOR_SIZE_CONSTANTS
    fake_eiger.beam_xy_converter = mock()

    test_detector_distance = 300.0
    test_beam_x_pixels = 1000.0
    test_beam_y_pixels = 1500.0
    when(fake_eiger.beam_xy_converter).get_beam_x_pixels(test_detector_distance, TEST_PIXELS_X_EIGER, TEST_EIGER_DIMENSION_X).thenReturn(test_beam_x_pixels)
    when(fake_eiger.beam_xy_converter).get_beam_y_pixels(test_detector_distance, TEST_PIXELS_Y_EIGER, TEST_EIGER_DIMENSION_Y).thenReturn(test_beam_y_pixels)

    expected_x = test_beam_x_pixels - TEST_PIXELS_X_EIGER + TEST_PIXELS_X_EIGER
    expected_y = test_beam_y_pixels - TEST_PIXELS_Y_EIGER + TEST_PIXELS_Y_EIGER

    assert fake_eiger.get_beam_position_pixels(test_detector_distance) == (expected_x, expected_y)


@pytest.mark.parametrize(
    "use_roi_mode, detector_size_constants, detector_params, beam_xy_converter",
    [
        (True, mock(), mock(), mock()),
        (True, None, mock(), mock()),
        (None, mock(), None, mock()),
        (None, None, None, mock()),
        (None, None, None, None)
    ]
)
def test_check_detector_variables(fake_eiger, use_roi_mode: bool, detector_size_constants, detector_params, beam_xy_converter):
    fake_eiger.detector_size_constants = detector_size_constants
    fake_eiger.use_roi_mode = use_roi_mode
    fake_eiger.detector_params = detector_params
    fake_eiger.beam_xy_converter = beam_xy_converter

    variables_to_check = [use_roi_mode, detector_size_constants, detector_params, beam_xy_converter]

    if not all(variables_to_check):
        with pytest.raises(Exception) as e:
            fake_eiger.check_detector_variables_set()
            number_of_none = sum(x is not None for x in variables_to_check)
            number_of_errors = e.value.count('\n') + 1

            assert e
            assert number_of_errors == number_of_none
    else:
        try:
            fake_eiger.check_detector_variables_set()
        except Exception as e:
            assert False, f"exception was raised {e}"
