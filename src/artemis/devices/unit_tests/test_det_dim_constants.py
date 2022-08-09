import pytest

from artemis.devices.det_dim_constants import (
    EIGER2_X_4M_DIMENSION_X,
    EIGER_TYPE_EIGER2_X_4M,
    constants_from_type,
)


def test_known_detector_gives_correct_type():
    det = constants_from_type(EIGER_TYPE_EIGER2_X_4M)
    assert det.det_dimension.width == EIGER2_X_4M_DIMENSION_X


def test_unknown_detector_raises_exception():
    with pytest.raises(KeyError):
        constants_from_type("BAD")
