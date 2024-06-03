import numpy as np
import pytest
from epicscorelibs.ca.dbr import ca_float, ca_int, ca_str

from hyperion.external_interaction.ispyb.ispyb_store import (
    _convert_subclasses_to_builtins,
)


@pytest.mark.parametrize(
    "input, expected",
    (
        (1.234, 1.234),
        (ca_float(1.234), 1.234),
        (1234, 1234),
        (ca_int(1234), 1234),
        ("test string", "test string"),
        (ca_str("test string"), "test string"),
        (None, None),
        (np.float_(1.234), 1.234),  # aka np.double/np.float64
        (np.int_(1234), 1234),
        (np.str_("test string"), "test string"),
    ),
)
def test_convert_to_builtin(input, expected):
    """
    See https://numpy.org/doc/stable/reference/arrays.scalars.html#sized-aliases
    for all the various types that exist; the above is not a complete set
    """
    input_list = [input]
    output_map = _convert_subclasses_to_builtins(input_list)
    actual = output_map[0]
    assert (
        actual == expected
    ), f"Conversion of {type(input)} {input} failed: {type(expected)} {expected} <=> {type(actual)} {actual}"
    assert type(actual) == type(expected)
