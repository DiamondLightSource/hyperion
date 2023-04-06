from dodal.parameters.experiment_parameter_base import AbstractExperimentParameterBase

from artemis.experiment_plans.experiment_registry import PLAN_REGISTRY


def test_experiment_registry_param_types():
    for plan in PLAN_REGISTRY.keys():
        assert issubclass(
            PLAN_REGISTRY[plan]["param_type"], AbstractExperimentParameterBase
        )
