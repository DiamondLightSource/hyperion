import numpy as np
import pytest

from artemis.utils import create_point


def test_create_point_on_invalid_number_of_args():
    with pytest.raises(TypeError):
        create_point(1)
    with pytest.raises(TypeError):
        create_point()
    with pytest.raises(TypeError):
        create_point(7, 45, 23, 2, 1, 4)


def test_create_point_creates_zero_array_given_none_type_args():
    np.testing.assert_equal(np.array([0, 0, 5]), create_point(None, None, 5))


def test_create_point_returns_correct_array_size():
    assert create_point(5, 2).shape == (2,)
    assert create_point(5, 2, 4).shape == (3,)
