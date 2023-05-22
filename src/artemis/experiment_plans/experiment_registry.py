from __future__ import annotations

from blueapi.core import MsgGenerator

from artemis.experiment_plans.fast_grid_scan_plan import fast_grid_scan  # noqa: F401
from artemis.experiment_plans.full_grid_scan import full_grid_scan  # noqa: F401
from artemis.parameters.internal_parameters.plan_specific.rotation_scan_internal_params import (
    RotationScanParams,
)


def rotation_scan(params: RotationScanParams) -> MsgGenerator:
    return NotImplemented
