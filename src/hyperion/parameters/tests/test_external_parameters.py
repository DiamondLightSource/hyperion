import pytest
from pydantic import ValidationError

from hyperion.parameters.external_parameters import (
    EXTERNAL_PARAMETERS_VERSION,
    ExternalDataParameters,
    ExternalExperimentParameters,
    HyperionExternalParameters,
    ParameterVersion,
)


@pytest.fixture
def blank_sub_params():
    return ExternalExperimentParameters(), ExternalDataParameters()


def test_version_takes_string_or_ParameterVersion(blank_sub_params):
    expt_params, data_params = blank_sub_params
    HyperionExternalParameters(
        parameter_version=ParameterVersion.parse("5.0.0"),
        experiment_parameters=expt_params,
        data_parameters=data_params,
    )
    HyperionExternalParameters(
        parameter_version="5.0.0",  # type: ignore
        experiment_parameters=expt_params,
        data_parameters=data_params,
    )


cur_maj_ver = EXTERNAL_PARAMETERS_VERSION.major
test_versions_and_successes = [
    (f"{cur_maj_ver}.0.0", True),
    (f"{cur_maj_ver}.0.1", True),
    (f"{cur_maj_ver}.4.17", True),
    (f"{cur_maj_ver}.1.0-pre.3", True),
    (f"{cur_maj_ver-1}.1.0", False),
    (f"{cur_maj_ver-1}.9", False),
    (f"{cur_maj_ver+1}.1", False),
    (f"{cur_maj_ver+1}.1.3a", False),
]


@pytest.mark.parametrize("version,success", test_versions_and_successes)
def test_external_parameter_version_validation(version, success, blank_sub_params):
    expt_params, data_params = blank_sub_params
    if success:
        HyperionExternalParameters(
            parameter_version=version,  # type: ignore
            experiment_parameters=expt_params,
            data_parameters=data_params,
        )
    else:
        with pytest.raises(ValidationError):
            HyperionExternalParameters(
                parameter_version=version,  # type: ignore
                experiment_parameters=expt_params,
                data_parameters=data_params,
            )
