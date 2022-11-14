import pytest

from artemis.devices.oav.oav_centring import OAVParameters


@pytest.mark.parametrize(
    "parameter_name,expected_value",
    [("canny_edge_lower_threshold", 5.0), ("close_ksize", 11), ("direction", 1)],
)
def test_oav_parameters_load_parameters_from_json(parameter_name, expected_value):
    parameters = OAVParameters("src/artemis/devices/unit_tests/test_OAVCentring.json")
    parameters.load_parameters_from_json()

    assert parameters.__dict__[parameter_name] == expected_value


def test_oav__extract_dict_parameter_not_found_fallback_value_present():
    parameters = OAVParameters("src/artemis/devices/unit_tests/test_OAVCentring.json")
    parameters.load_json()
    assert (
        parameters._extract_dict_parameter(
            "loopCentring", "a_key_not_in_the_json", fallback_value=1
        )
        == 1
    )


def test_oav__extract_dict_parameter_not_found_fallback_value_not_present():
    parameters = OAVParameters("src/artemis/devices/unit_tests/test_OAVCentring.json")
    parameters.load_json()
    with pytest.raises(KeyError):
        parameters._extract_dict_parameter("loopCentring", "a_key_not_in_the_json")
