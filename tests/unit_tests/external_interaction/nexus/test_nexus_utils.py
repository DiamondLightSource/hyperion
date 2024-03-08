import numpy as np
import pytest
from numpy.typing import DTypeLike

from hyperion.external_interaction.nexus.nexus_utils import vds_type_based_on_bit_depth


@pytest.mark.parametrize(
    "bit_depth,expected_type",
    [(8, np.uint8), (16, np.uint16), (32, np.uint32), (100, np.uint16)],
)
def test_vds_type_is_expected_based_on_bit_depth(
    bit_depth: int, expected_type: DTypeLike
):
    assert vds_type_based_on_bit_depth(bit_depth) == expected_type
