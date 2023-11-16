from __future__ import annotations

from dodal.parameters.experiment_parameter_base import AbstractExperimentParameterBase
from pydantic.dataclasses import dataclass

from hyperion.external_interaction.ispyb.ispyb_dataclass import (
    GridscanIspybParams,
)
from hyperion.parameters.external_parameters import ExternalParameters
from hyperion.parameters.internal_parameters import (
    InternalParameters,
)


@dataclass
class GridScanWithEdgeDetectParams(AbstractExperimentParameterBase):
    """
    Holder class for the parameters of a grid scan that uses edge detection to detect the grid.
    """

    exposure_time: float
    snapshot_dir: str
    detector_distance_mm: float
    omega_start_deg: float

    # This is the correct grid size for single pin
    grid_width_microns: float = 600

    def get_num_images(self):
        return 0


class GridScanWithEdgeDetectInternalParameters(InternalParameters):
    experiment_params: GridScanWithEdgeDetectParams
    ispyb_params: GridscanIspybParams

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def from_external(cls, external: ExternalParameters):
        return cls(
            params_version=external.parameter_version,
            ispyb_params=GridscanIspybParams.from_external(external),
            experiment_params=GridScanWithEdgeDetectParams(
                **external.data_parameters.dict(),
                **external.experiment_parameters.dict(),
            ),
        )

    def get_data_shape(self):
        raise TypeError("Data shape does not apply to this type of experiment!")

    def get_scan_points(self):
        raise TypeError("Scan points do not apply to this type of experiment!")
