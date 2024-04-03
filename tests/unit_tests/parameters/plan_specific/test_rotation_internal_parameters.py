from unittest.mock import MagicMock

import numpy as np
import pytest
from dodal.devices.detector.det_dim_constants import EIGER2_X_16M_SIZE
from dodal.devices.motors import XYZLimitBundle

from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
    RotationScanParams,
)

from ....conftest import raw_params_from_file


def test_rotation_scan_param_validity():
    test_params = RotationScanParams(
        rotation_axis="omega",
        rotation_angle=360,
        image_width=0.1,
        omega_start=0,
        phi_start=0,
        chi_start=0,
        kappa_start=0,
        x=0,
        y=0,
        z=0,
    )

    xlim = MagicMock()
    ylim = MagicMock()
    zlim = MagicMock()
    lims = XYZLimitBundle(xlim, ylim, zlim)

    assert test_params.xyz_are_valid(lims)
    zlim.is_within.return_value = False
    assert not test_params.xyz_are_valid(lims)
    zlim.is_within.return_value = True
    ylim.is_within.return_value = False
    assert not test_params.xyz_are_valid(lims)
    ylim.is_within.return_value = True
    xlim.is_within.return_value = False
    assert not test_params.xyz_are_valid(lims)


def test_rotation_parameters_load_from_file():
    params = raw_params_from_file(
        "tests/test_data/parameter_json_files/good_test_rotation_scan_parameters.json"
    )
    internal_parameters = RotationInternalParameters(**params)

    assert isinstance(internal_parameters.experiment_params, RotationScanParams)
    assert internal_parameters.experiment_params.rotation_direction == "Negative"

    ispyb_params = internal_parameters.hyperion_params.ispyb_params

    np.testing.assert_array_equal(ispyb_params.position, np.array([10, 20, 30]))
    with pytest.raises(AttributeError):
        ispyb_params.upper_left

    detector_params = internal_parameters.hyperion_params.detector_params

    assert detector_params.detector_size_constants == EIGER2_X_16M_SIZE
    assert detector_params.expected_energy_ev == 100


def test_rotation_parameters_enum_interpretation():
    params = raw_params_from_file(
        "tests/test_data/parameter_json_files/good_test_rotation_scan_parameters.json"
    )
    params["experiment_params"]["rotation_direction"] = "Positive"
    internal_parameters = RotationInternalParameters(**params)
    assert isinstance(internal_parameters.experiment_params, RotationScanParams)

    assert internal_parameters.experiment_params.rotation_direction == "Positive"
