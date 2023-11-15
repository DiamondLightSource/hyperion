from abc import abstractmethod

from dodal.devices.eiger import DetectorParams
from dodal.parameters.experiment_parameter_base import AbstractExperimentParameterBase
from dodal.utils import BeamlinePrefix, get_beamline_name
from pydantic import BaseModel

from hyperion.external_interaction.ispyb.ispyb_dataclass import IspybParams
from hyperion.parameters.external_parameters import ExternalParameters, ParameterVersion


class InternalParameters(BaseModel):
    params_version: ParameterVersion

    detector_params: DetectorParams
    experiment_params: AbstractExperimentParameterBase
    ispyb_params: IspybParams

    beamline: str
    experiment_type: str
    insertion_prefix: str
    zocalo_environment: str

    class Config:
        use_enum_values = True
        arbitrary_types_allowed = True
        json_encoders = {
            ParameterVersion: lambda pv: str(pv),
        }

    @staticmethod
    def _common_from_external(external: ExternalParameters):
        data_params = external.data_parameters.dict()
        expt_params = external.experiment_parameters.dict()
        expt_params.update(
            {
                "detector_size_constants": external.experiment_parameters.detector,
                "current_energy_ev": external.experiment_parameters.energy_ev,
            }
        )
        assert (
            external.experiment_type is not None
        ), "Can't initialise InternalParameters from ExternalParameters without set 'experiment_type' field."
        zocalo_environment = (
            external.data_parameters.zocalo_environment or "artemis-dev"
        )
        beamline = external.data_parameters.beamline or get_beamline_name("i03")
        insertion_prefix = (
            external.data_parameters.insertion_prefix
            or BeamlinePrefix(get_beamline_name("i03")).insertion_prefix
        )
        experiment_type = external.experiment_type
        return (
            data_params,
            expt_params,
            zocalo_environment,
            beamline,
            insertion_prefix,
            experiment_type,
        )

    @classmethod
    @abstractmethod
    def from_external(cls, external: ExternalParameters):
        ...

    @abstractmethod
    def get_scan_points(cls) -> dict[str, list]:
        """Get points of the scan as calculated by scanspec."""
        ...

    @abstractmethod
    def get_data_shape(cls) -> tuple[int, int, int]:
        """Get the shape of the data resulting from the experiment specified by
        these parameters."""
        ...
