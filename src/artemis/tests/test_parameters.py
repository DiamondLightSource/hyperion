from artemis.parameters import FullParameters


def test_new_parameters_is_a_deep_copy():
    first_copy = FullParameters()
    second_copy = FullParameters()

    assert (
        first_copy.artemis_params.detector_params
        is not second_copy.artemis_params.detector_params
    )
    assert first_copy.experiment_params is not second_copy.experiment_params
    assert (
        first_copy.artemis_params.ispyb_params
        is not second_copy.artemis_params.ispyb_params
    )
