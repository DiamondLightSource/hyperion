from __future__ import annotations

from typing import Any

import numpy as np
from dodal.devices.detector import DetectorParams
from dodal.devices.motors import XYZLimitBundle
from dodal.devices.zebra import RotationDirection
from dodal.parameters.experiment_parameter_base import AbstractExperimentWithBeamParams
from pydantic import validator
from scanspec.core import Path as ScanPath
from scanspec.specs import Line

from hyperion.external_interaction.ispyb.ispyb_dataclass import (
    GRIDSCAN_ISPYB_PARAM_DEFAULTS,
    RotationIspybParams,
)
from hyperion.parameters.internal_parameters import (
    HyperionParameters,
    InternalParameters,
    extract_experiment_params_from_flat_dict,
    extract_hyperion_params_from_flat_dict,
)


class RotationHyperionParameters(HyperionParameters):
    ispyb_params: RotationIspybParams = RotationIspybParams(
        **GRIDSCAN_ISPYB_PARAM_DEFAULTS
    )

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            **DetectorParams.Config.json_encoders,
            **RotationIspybParams.Config.json_encoders,
        }


class RotationScanParams(AbstractExperimentWithBeamParams):
    """
    Holder class for the parameters of a rotation data collection.
    """

    rotation_axis: str = "omega"
    rotation_angle: float = 360.0
    image_width: float = 0.1
    omega_start: float = 0.0
    phi_start: float | None = None
    chi_start: float | None = None
    kappa_start: float | None = None
    x: float | None = None
    y: float | None = None
    z: float | None = None
    rotation_direction: RotationDirection = RotationDirection.NEGATIVE
    shutter_opening_time_s: float = 0.6

    @validator("rotation_direction", pre=True)
    def _parse_direction(cls, rotation_direction: str):
        return RotationDirection(rotation_direction)

    def xyz_are_valid(self, limits: XYZLimitBundle) -> bool:
        """
        Validates scan location in x, y, and z

        :param limits: The motor limits against which to validate
                       the parameters
        :return: True if the scan is valid
        """
        assert (
            self.x is not None and self.y is not None and self.z is not None
        ), "Validity is only defined for positions which are not None"
        return (
            limits.x.is_within(self.x)
            and limits.y.is_within(self.y)
            and limits.z.is_within(self.z)
        )

    def get_num_images(self) -> int:
        return int(self.rotation_angle / self.image_width)


class RotationInternalParameters(InternalParameters):
    experiment_params: RotationScanParams
    hyperion_params: RotationHyperionParameters

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            **RotationHyperionParameters.Config.json_encoders,
        }

    @staticmethod
    def _hyperion_param_key_definitions() -> tuple[list[str], list[str], list[str]]:
        (
            hyperion_param_field_keys,
            detector_field_keys,
            ispyb_field_keys,
        ) = InternalParameters._hyperion_param_key_definitions()
        ispyb_field_keys += list(RotationIspybParams.__annotations__.keys())

        return hyperion_param_field_keys, detector_field_keys, ispyb_field_keys

    @validator("experiment_params", pre=True)
    def _preprocess_experiment_params(
        cls,
        experiment_params: dict[str, Any],
    ):
        if isinstance(experiment_params, RotationScanParams):
            return experiment_params
        return RotationScanParams(
            **extract_experiment_params_from_flat_dict(
                RotationScanParams, experiment_params
            )
        )

    @validator("hyperion_params", pre=True)
    def _preprocess_hyperion_params(
        cls, all_params: dict[str, Any], values: dict[str, Any]
    ):
        if isinstance(all_params.get("hyperion_params"), RotationHyperionParameters):
            return all_params["hyperion_params"]
        experiment_params: RotationScanParams = values["experiment_params"]
        all_params["num_images"] = experiment_params.get_num_images()
        all_params["position"] = np.array(all_params["position"])
        if (
            all_params["rotation_axis"] == "omega"
            and all_params.get("rotation_increment") is not None
        ):
            all_params["omega_increment"] = all_params["rotation_increment"]
        else:
            all_params["omega_increment"] = 0
        all_params["num_triggers"] = 1
        all_params["num_images_per_trigger"] = all_params["num_images"]
        all_params["current_energy_ev"] = all_params["expected_energy_ev"]
        return RotationHyperionParameters(
            **extract_hyperion_params_from_flat_dict(
                all_params, cls._hyperion_param_key_definitions()
            )
        )

    def get_scan_points(self):
        scan_spec = Line(
            axis="omega",
            start=self.experiment_params.omega_start,
            stop=(
                self.experiment_params.rotation_angle
                + self.experiment_params.omega_start
            ),
            num=self.experiment_params.get_num_images(),
        )
        scan_path = ScanPath(scan_spec.calculate())
        return scan_path.consume().midpoints

    def get_data_shape(self) -> tuple[int, int, int]:
        size = (
            self.hyperion_params.detector_params.detector_size_constants.det_size_pixels
        )
        return (self.experiment_params.get_num_images(), size.width, size.height)
