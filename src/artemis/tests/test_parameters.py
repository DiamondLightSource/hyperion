from src.artemis.parameters import FullParameters


def test_new_parameters_is_a_deep_copy():
    first_copy = FullParameters()
    second_copy = FullParameters()

    assert first_copy.detector_params is not second_copy.detector_params
    assert first_copy.grid_scan_params is not second_copy.grid_scan_params
    assert first_copy.ispyb_params is not second_copy.ispyb_params
