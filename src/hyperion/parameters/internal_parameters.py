from abc import abstractmethod

from dodal.devices.eiger import DetectorParams
from dodal.parameters.experiment_parameter_base import AbstractExperimentParameterBase
from dodal.utils import BeamlinePrefix, get_beamline_name
from pydantic import BaseModel, Extra

from hyperion.external_interaction.ispyb.ispyb_dataclass import IspybParams
from hyperion.parameters.external_parameters import ExternalParameters, ParameterVersion


class HyperionParameters(BaseModel):
    zocalo_environment: str
    beamline: str
    insertion_prefix: str
    experiment_type: str
    detector_params: DetectorParams

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            **DetectorParams.Config.json_encoders,
            **IspybParams.Config.json_encoders,
        }
        extra = Extra.ignore

    @classmethod
    def from_external(cls, external: ExternalParameters):
        assert (
            external._experiment_type is not None
        ), "Can't initialise HyperionParameters from ExternalParameters without set '_experiment_type' field."
        return cls(
            zocalo_environment=external.data_parameters.zocalo_environment
            or "artemis-dev",
            beamline=external.data_parameters.beamline or get_beamline_name("i03"),
            insertion_prefix=external.data_parameters.insertion_prefix
            or BeamlinePrefix(get_beamline_name("i03")).insertion_prefix,
            experiment_type=external._experiment_type,
            detector_params=DetectorParams(
                **external.data_parameters.dict(),
                **external.experiment_parameters.dict(),
            ),
        )


class InternalParameters(BaseModel):
    params_version: ParameterVersion
    hyperion_params: HyperionParameters
    ispyb_params: IspybParams
    experiment_params: AbstractExperimentParameterBase

    class Config:
        use_enum_values = True
        arbitrary_types_allowed = True
        json_encoders = {
            ParameterVersion: lambda pv: str(pv),
        }

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
