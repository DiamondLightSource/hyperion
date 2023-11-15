from __future__ import annotations

from typing import Any

import numpy as np
from dodal.devices.detector import TriggerMode
from dodal.parameters.experiment_parameter_base import AbstractExperimentParameterBase
from pydantic import validator
from pydantic.dataclasses import dataclass

from hyperion.external_interaction.ispyb.ispyb_dataclass import GridscanIspybParams
from hyperion.parameters.external_parameters import ExternalParameters
from hyperion.parameters.internal_parameters import (
    HyperionParameters,
    InternalParameters,
)


@dataclass
class PinCentreThenXrayCentreParams(AbstractExperimentParameterBase):
    """
    Holder class for the parameters of a plan that does a pin centre then xray centre
    """

    exposure_time: float
    snapshot_dir: str
    detector_distance: float
    omega_start: float

    tip_offset_microns: float = 0
    oav_centring_file: str = "/dls_sw/i03/software/gda/configurations/i03-config/etc/OAVCentring_hyperion.json"

    # Width for single pin
    grid_width_microns: float = 600

    def get_num_images(self):
        return 0


class PinCentreThenXrayCentreInternalParameters(InternalParameters):
    experiment_params: PinCentreThenXrayCentreParams
    ispyb_params: GridscanIspybParams

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            **HyperionParameters.Config.json_encoders,
        }

    @classmethod
    def from_external(cls, external: ExternalParameters):
        return cls(
            params_version=external.parameter_version,
            hyperion_params=HyperionParameters.from_external(external),
            ispyb_params=GridscanIspybParams.from_external(external),
            experiment_params=PinCentreThenXrayCentreParams(
                **external.data_parameters.dict(),
                **external.experiment_parameters.dict(),
            ),
        )

    def get_data_shape(self):
        raise TypeError("Data shape does not apply to this type of experiment!")

    def get_scan_points(self):
        raise TypeError("Scan points do not apply to this type of experiment!")
