from __future__ import annotations

from typing import Any

from artemis.parameters.internal_parameters import InternalParameters
from dataclasses_json import DataClassJsonMixin
from dodal.parameters.experiment_parameter_base import AbstractExperimentParameterBase
from dodal.devices.motors import XYZLimitBundle
from dataclasses import dataclass
import numpy as np


@dataclass
class GridAxis:
    start: float
    step_size: float
    full_steps: int

    def steps_to_motor_position(self, steps):
        return self.start + (steps * self.step_size)

    @property
    def end(self):
        return self.steps_to_motor_position(self.full_steps)

    def is_within(self, steps):
        return 0 <= steps <= self.full_steps


@dataclass
class SteppedGridScanParams(DataClassJsonMixin, AbstractExperimentParameterBase):
    """
    Holder class for the parameters of a grid scan.
    """

    x_steps: int = 1
    y_steps: int = 1
    z_steps: int = 0
    x_step_size: float = 0.1
    y_step_size: float = 0.1
    z_step_size: float = 0.1
    dwell_time: float = 0.1
    x_start: float = 0.1
    y1_start: float = 0.1
    y2_start: float = 0.1
    z1_start: float = 0.1
    z2_start: float = 0.1

    def __post_init__(self):
        self.x_axis = GridAxis(self.x_start, self.x_step_size, self.x_steps)
        self.y_axis = GridAxis(self.y1_start, self.y_step_size, self.y_steps)
        self.z_axis = GridAxis(self.z2_start, self.z_step_size, self.z_steps)
        self.axes = [self.x_axis, self.y_axis, self.z_axis]

    def is_valid(self, limits: XYZLimitBundle) -> bool:
        """
        Validates scan parameters
        :param limits: The motor limits against which to validate
                       the parameters
        :return: True if the scan is valid
        """
        x_in_limits = limits.x.is_within(self.x_axis.start) and limits.x.is_within(
            self.x_axis.end
        )
        y_in_limits = limits.y.is_within(self.y_axis.start) and limits.y.is_within(
            self.y_axis.end
        )

        first_grid_in_limits = (
            x_in_limits and y_in_limits and limits.z.is_within(self.z1_start)
        )

        z_in_limits = limits.z.is_within(self.z_axis.start) and limits.z.is_within(
            self.z_axis.end
        )

        second_grid_in_limits = (
            x_in_limits and z_in_limits and limits.y.is_within(self.y2_start)
        )

        return first_grid_in_limits and second_grid_in_limits

    def get_num_images(self):
        return self.x_steps * self.y_steps + self.y_steps * self.z_steps

    @property
    def is_3d_grid_scan(self):
        return self.z_steps > 0

    def grid_position_to_motor_position(self, grid_position: np.ndarray) -> np.ndarray:
        """Converts a grid position, given as steps in the x, y, z grid,
        to a real motor position.
        :param grid_position: The x, y, z position in grid steps
        :return: The motor position this corresponds to.
        :raises: IndexError if the desired position is outside the grid."""
        for position, axis in zip(grid_position, self.axes):
            if not axis.is_within(position):
                raise IndexError(f"{grid_position} is outside the bounds of the grid")

        return np.array([
            self.x_axis.steps_to_motor_position(grid_position[0]),
            self.y_axis.steps_to_motor_position(grid_position[1]),
            self.z_axis.steps_to_motor_position(grid_position[2]),
        ])


class SteppedGridScanInternalParameters(InternalParameters):
    experiment_params_type = SteppedGridScanParams
    experiment_params: SteppedGridScanParams

    def artemis_param_preprocessing(self, param_dict: dict[str, Any]):
        super().artemis_param_preprocessing(param_dict)
        param_dict["omega_increment"] = 0
        param_dict["num_triggers"] = param_dict["num_images"]
        param_dict["num_images_per_trigger"] = 1
