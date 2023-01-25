from artemis.devices.det_dim_constants import constants_from_type
from artemis.devices.eiger import DETECTOR_PARAM_DEFAULTS, DetectorParams
from artemis.external_interaction.ispyb.ispyb_dataclass import (
    ISPYB_PARAM_DEFAULTS,
    IspybParams,
)
from artemis.parameters.constants import (
    EXPERIMENT_DICT,
    EXPERIMENT_NAMES,
    EXPERIMENT_TYPES,
    SIM_BEAMLINE,
    SIM_INSERTION_PREFIX,
    SIM_ZOCALO_ENV,
)
from artemis.parameters.external_parameters import RawParameters
from artemis.utils import Point3D


class ArtemisParameters:
    zocalo_environment: str = SIM_ZOCALO_ENV
    beamline: str = SIM_BEAMLINE
    insertion_prefix: str = SIM_INSERTION_PREFIX
    experiment_type: str = EXPERIMENT_NAMES[0]
    detector_params: DetectorParams = DetectorParams(**DETECTOR_PARAM_DEFAULTS)

    ispyb_params: IspybParams = IspybParams(**ISPYB_PARAM_DEFAULTS)

    def __init__(
        self,
        zocalo_environment: str = SIM_ZOCALO_ENV,
        beamline: str = SIM_BEAMLINE,
        insertion_prefix: str = SIM_INSERTION_PREFIX,
        experiment_type: str = EXPERIMENT_NAMES[0],
        detector_params: DetectorParams = DetectorParams(**DETECTOR_PARAM_DEFAULTS),
        ispyb_params: IspybParams = IspybParams(**ISPYB_PARAM_DEFAULTS),
    ) -> None:
        self.zocalo_environment = zocalo_environment
        self.beamline = beamline
        self.insertion_prefix = insertion_prefix
        self.experiment_type = experiment_type
        self.detector_params = detector_params
        self.ispyb_params = ispyb_params

    def __eq__(self, other) -> bool:
        if not isinstance(other, ArtemisParameters):
            return NotImplemented
        elif self.zocalo_environment != other.zocalo_environment:
            return False
        elif self.beamline != other.beamline:
            return False
        elif self.insertion_prefix != other.insertion_prefix:
            return False
        elif self.experiment_type != other.experiment_type:
            return False
        elif self.detector_params != other.detector_params:
            return False
        elif self.ispyb_params != other.ispyb_params:
            return False
        return True


class InternalParameters:
    artemis_params: ArtemisParameters
    experiment_params: EXPERIMENT_TYPES
    fully_initialised: bool = False

    def __init__(self, external_params: RawParameters = RawParameters()):
        all_params_bucket = {
            **(external_params["artemis_params"]["ispyb_params"]),
            **(external_params["artemis_params"]["detector_params"]),
            **(external_params["experiment_params"]),
        }
        detector_field_keys = DetectorParams.__annotations__.keys()
        ispyb_field_keys = IspybParams.__annotations__.keys()

        detector_params_args = {
            key: all_params_bucket.get(key)
            for key in detector_field_keys
            if all_params_bucket.get(key) is not None
        }
        ispyb_params_args = {
            key: all_params_bucket.get(key)
            for key in ispyb_field_keys
            if all_params_bucket.get(key) is not None
        }

        self.artemis_params = ArtemisParameters(
            **external_params.params["artemis_params"]
        )

        self.artemis_params.ispyb_params = IspybParams(**ispyb_params_args)
        self.artemis_params.ispyb_params.upper_left = Point3D(
            *self.artemis_params.ispyb_params.upper_left
        )
        self.artemis_params.ispyb_params.position = Point3D(
            *self.artemis_params.ispyb_params.position
        )
        self.experiment_params = EXPERIMENT_DICT[ArtemisParameters.experiment_type](
            **external_params["experiment_params"]
        )
        detector_params_args["num_images"] = self.experiment_params.get_num_images()

        self.artemis_params.detector_params = DetectorParams(**detector_params_args)
        self.artemis_params.detector_params.detector_size_constants = (
            constants_from_type(
                self.artemis_params.detector_params.detector_size_constants
            )
        )

    def check_fully_initialised(self) -> bool:
        self.fully_initialised = (
            self.artemis_params.detector_params.check_fully_initialised()
            & self.artemis_params.ispyb_params.check_fully_initialised()
        )

        return self.fully_initialised

    def __eq__(self, other) -> bool:
        if not isinstance(other, InternalParameters):
            return NotImplemented
        if self.artemis_params != other.artemis_params:
            return False
        if self.experiment_params != other.experiment_params:
            return False
        return True

    @classmethod
    def from_external_json(cls, json_data):
        """Convenience method to generate from external parameter JSON blob, uses
        RawParameters.from_json()"""
        return cls(RawParameters.from_json(json_data))

    @classmethod
    def from_external_dict(cls, dict_data):
        """Convenience method to generate from external parameter dictionary, uses
        RawParameters.from_dict()"""
        return cls(RawParameters.from_dict(dict_data))
