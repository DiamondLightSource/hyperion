from copy import deepcopy

import numpy as np
import pytest

from hyperion.external_interaction.ispyb.ispyb_dataclass import (
    GRIDSCAN_ISPYB_PARAM_DEFAULTS,
    IspybParams,
)


def test_given_position_as_list_when_ispyb_params_created_then_converted_to_numpy_array():
    params = deepcopy(GRIDSCAN_ISPYB_PARAM_DEFAULTS)
    params["position"] = [1, 2, 3]

    ispyb_params = IspybParams(**params)

    assert isinstance(ispyb_params.position, np.ndarray)
    assert np.array_equal(ispyb_params.position, [1, 2, 3])


def test_given_ispyb_params_when_converted_to_dict_then_position_is_a_list():
    params = deepcopy(GRIDSCAN_ISPYB_PARAM_DEFAULTS)
    params["position"] = [1, 2, 3]

    ispyb_params_dict = IspybParams(**params).dict()

    assert isinstance(ispyb_params_dict["position"], list)
    assert ispyb_params_dict["position"] == [1, 2, 3]


def test_given_transmission_greater_than_1_when_ispyb_params_created_then_throws_exception():
    params = deepcopy(GRIDSCAN_ISPYB_PARAM_DEFAULTS)
    params["transmission_fraction"] = 20.5

    with pytest.raises(ValueError):
        IspybParams(**params)
