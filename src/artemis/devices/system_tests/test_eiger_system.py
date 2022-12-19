import pytest

from artemis.devices.eiger import DetectorParams, EigerDetector


@pytest.fixture()
def eiger():
    detector_params: DetectorParams = DetectorParams(
        current_energy=100,
        exposure_time=0.1,
        directory="/tmp",
        prefix="file_name",
        detector_distance=100.0,
        omega_start=0.0,
        omega_increment=0.1,
        num_images=50,
        use_roi_mode=False,
        run_number=0,
        det_dist_to_beam_converter_path="src/artemis/devices/unit_tests/test_lookup_table.txt",
    )
    eiger = EigerDetector(
        detector_params=detector_params, name="eiger", prefix="BL03S-EA-EIGER-01:"
    )

    # Otherwise odin moves too fast to be tested
    eiger.cam.manual_trigger.put("Yes")

    # S03 currently does not have StaleParameters_RBV
    eiger.wait_for_stale_parameters = lambda: None

    yield eiger


@pytest.mark.skip(reason="Eiger/odin is broken in S03")
@pytest.mark.s03
def test_can_stage_and_unstage_eiger(eiger: EigerDetector):
    eiger.stage()
    assert eiger.cam.acquire.get() == 1
    # S03 filewriters stay in error
    eiger.odin.check_odin_initialised = lambda: (True, "")
    eiger.unstage()
    assert eiger.cam.acquire.get() == 0
