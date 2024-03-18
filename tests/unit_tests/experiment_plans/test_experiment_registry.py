from dodal.parameters.experiment_parameter_base import AbstractExperimentWithBeamParams

from hyperion.experiment_plans.experiment_registry import PLAN_REGISTRY, do_nothing
from hyperion.parameters.internal_parameters import InternalParameters


def test_experiment_registry_param_types():
    for plan in PLAN_REGISTRY.keys():
        assert issubclass(
            PLAN_REGISTRY[plan]["experiment_param_type"],
            AbstractExperimentWithBeamParams,
        )
        assert issubclass(
            PLAN_REGISTRY[plan]["internal_param_type"], InternalParameters
        )


def test_do_nothing():
    do_nothing()
