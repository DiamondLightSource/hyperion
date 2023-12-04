from pytest import mark

from hyperion.utils.lookup_table import (
    LinearInterpolationLUTConverter,
    PerpRollLUTConverter,
)


@mark.parametrize("s, expected_t", [(2.0, 1.0), (3.0, 1.5), (5.0, 4.0), (5.25, 6.0)])
def test_linear_interpolation(s, expected_t):
    lut_converter = LinearInterpolationLUTConverter(
        "tests/test_data/test_beamline_dcm_roll_converter.txt"
    )
    assert lut_converter.s_to_t(s) == expected_t


@mark.parametrize("s, expected_t", [(2.0, 1.0), (3.0, 1.5), (5.0, 4.0), (5.25, 6.0)])
def test_linear_interpolation_reverse_order(s, expected_t):
    lut_converter = LinearInterpolationLUTConverter(
        "tests/test_data/test_beamline_dcm_roll_converter_reversed.txt"
    )
    actual_t = lut_converter.s_to_t(s)
    assert actual_t == expected_t, f"actual {actual_t} != expected {expected_t}"


@mark.parametrize(
    "s, expected_t", [(5, 1.01225), (8.95813, 0.905647), (10.0, 0.86717), (15, 0.61905)]
)
def test_perp_roll_lut_converter(s, expected_t):
    lut_converter = PerpRollLUTConverter()
    assert abs(lut_converter.s_to_t(s) - expected_t) < 1e-3
