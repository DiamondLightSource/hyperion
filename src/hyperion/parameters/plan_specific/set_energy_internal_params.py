from typing import Any

from hyperion.parameters.internal_parameters import InternalParameters


class SetEnergyParams:
    pass


class SetEnergyInternalParameters(InternalParameters):
    def _preprocess_experiment_params(cls, experiment_params: dict[str, Any]):
        pass

    def _preprocess_hyperion_params(
        cls, all_params: dict[str, Any], values: dict[str, Any]
    ):
        pass

    def get_scan_points(cls) -> dict[str, list]:
        pass

    def get_data_shape(cls) -> tuple[int, int, int]:
        pass
