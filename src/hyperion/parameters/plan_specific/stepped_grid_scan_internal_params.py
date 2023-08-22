from __future__ import annotations

from typing import Any

import numpy as np
from dodal.devices.motors import XYZLimitBundle
from dodal.parameters.experiment_parameter_base import AbstractExperimentParameterBase
from pydantic import validator
from pydantic.dataclasses import dataclass
from scanspec.core import Path as ScanPath
from scanspec.specs import Line

from hyperion.parameters.internal_parameters import (
    HyperionParameters,
    InternalParameters,
    extract_hyperion_params_from_flat_dict,
    extract_experiment_params_from_flat_dict,
)


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
class SteppedGridScanParams(AbstractExperimentParameterBase):
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

        return np.array(
            [
                self.x_axis.steps_to_motor_position(grid_position[0]),
                self.y_axis.steps_to_motor_position(grid_position[1]),
                self.z_axis.steps_to_motor_position(grid_position[2]),
            ]
        )


class SteppedGridScanInternalParameters(InternalParameters):
    experiment_params: SteppedGridScanParams
    hyperion_params: HyperionParameters

    @validator("experiment_params", pre=True)
    def _preprocess_experiment_params(
        cls,
        experiment_params: dict[str, Any],
    ):
        return SteppedGridScanParams(
            **extract_experiment_params_from_flat_dict(
                SteppedGridScanParams, experiment_params
            )
        )

    @validator("hyperion_params", pre=True)
    def _preprocess_hyperion_params(
        cls, all_params: dict[str, Any], values: dict[str, Any]
    ):
        experiment_params: SteppedGridScanParams = values["experiment_params"]
        all_params["num_images"] = experiment_params.get_num_images()
        all_params["omega_increment"] = 0
        all_params["num_images_per_trigger"] = 1

        return HyperionParameters(
            **extract_hyperion_params_from_flat_dict(
                all_params, cls._hyperion_param_key_definitions()
            )
        )

    def get_scan_points(self, scan_number: int) -> dict:
        """Get the scan points for the first or second gridscan: scan number must be
        1 or 2"""

        def create_line(name: str, axis: GridAxis):
            return Line(name, axis.start, axis.end, axis.full_steps)

        if scan_number == 1:
            x_line = create_line("sam_x", self.experiment_params.x_axis)
            y_line = create_line("sam_y", self.experiment_params.y_axis)
            spec = y_line * ~x_line
        elif scan_number == 2:
            x_line = create_line("sam_x", self.experiment_params.x_axis)
            z_line = create_line("sam_z", self.experiment_params.z_axis)
            spec = z_line * ~x_line
        else:
            raise Exception("Cannot provide scan points for other scans than 1 or 2")

        scan_path = ScanPath(spec.calculate())
        return scan_path.consume().midpoints

    def get_data_shape(self, scan_points: dict) -> tuple[int, int, int]:
        size = (
            self.hyperion_params.detector_params.detector_size_constants.det_size_pixels
        )
        ax = list(scan_points.keys())[0]
        num_frames_in_vds = len(scan_points[ax])
        return (num_frames_in_vds, size.width, size.height)
