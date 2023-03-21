from typing import Any, Dict

from dodal.devices.eiger import DetectorParams
from dodal.parameters.experiment_parameter_base import AbstractExperimentParameterBase

import artemis.experiment_plans.experiment_registry as registry
from artemis.external_interaction.ispyb.ispyb_dataclass import (
    ISPYB_PARAM_DEFAULTS,
    IspybParams,
)
from artemis.parameters.constants import (
    DETECTOR_PARAM_DEFAULTS,
    SIM_BEAMLINE,
    SIM_INSERTION_PREFIX,
    SIM_ZOCALO_ENV,
)
from artemis.parameters.external_parameters import EigerTriggerModes, RawParameters


class ArtemisParameters:
    zocalo_environment: str = SIM_ZOCALO_ENV
    beamline: str = SIM_BEAMLINE
    insertion_prefix: str = SIM_INSERTION_PREFIX
    experiment_type: str = registry.EXPERIMENT_NAMES[0]

    detector_params: DetectorParams = DetectorParams.from_dict(DETECTOR_PARAM_DEFAULTS)
    ispyb_params: IspybParams = IspybParams.from_dict(ISPYB_PARAM_DEFAULTS)

    def __init__(
        self,
        zocalo_environment: str = SIM_ZOCALO_ENV,
        beamline: str = SIM_BEAMLINE,
        insertion_prefix: str = SIM_INSERTION_PREFIX,
        experiment_type: str = registry.EXPERIMENT_NAMES[0],
        detector_params: Dict[str, Any] = DETECTOR_PARAM_DEFAULTS,
        ispyb_params: Dict[str, Any] = ISPYB_PARAM_DEFAULTS,
    ) -> None:
        self.zocalo_environment = zocalo_environment
        self.beamline = beamline
        self.insertion_prefix = insertion_prefix
        self.experiment_type = experiment_type
        self.detector_params: DetectorParams = DetectorParams.from_dict(detector_params)
        self.ispyb_params: IspybParams = IspybParams.from_dict(ispyb_params)

    def __repr__(self):
        r = "artemis_params:\n"
        r += f"    zocalo_environment: {self.zocalo_environment}\n"
        r += f"    beamline: {self.beamline}\n"
        r += f"    insertion_prefix: {self.insertion_prefix}\n"
        r += f"    experiment_type: {self.experiment_type}\n"
        r += f"    detector_params: {self.detector_params}\n"
        r += f"    ispyb_params: {self.ispyb_params}\n"
        return r

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
    experiment_params: registry.EXPERIMENT_TYPES

    def __init__(self, external_params: RawParameters = RawParameters()):
        ext_expt_param_dict = external_params.experiment_params.to_dict()
        ext_art_param_dict = external_params.artemis_params.to_dict()

        omeg_inc = ext_expt_param_dict.get("omega_increment")
        if omeg_inc is not None:
            ext_art_param_dict["detector_params"]["omega_increment"] = omeg_inc
            del ext_expt_param_dict["omega_increment"]
        else:
            ext_art_param_dict["detector_params"][
                "omega_increment"
            ] = ext_expt_param_dict["rotation_increment"]

        ext_art_param_dict["detector_params"]["omega_start"] = ext_expt_param_dict[
            "omega_start"
        ]
        del ext_expt_param_dict["omega_start"]

        ext_art_param_dict["detector_params"][
            "detector_distance"
        ] = ext_expt_param_dict["detector_distance"]
        del ext_expt_param_dict["detector_distance"]

        ext_art_param_dict["detector_params"]["exposure_time"] = ext_expt_param_dict[
            "exposure_time"
        ]
        del ext_expt_param_dict["exposure_time"]

        self.experiment_params: AbstractExperimentParameterBase = (
            registry.EXPERIMENT_TYPE_DICT[ext_art_param_dict["experiment_type"]](
                **ext_expt_param_dict
            )
        )

        n_images = self.experiment_params.get_num_images()
        if (
            ext_art_param_dict["detector_params"]["trigger_mode"]
            == EigerTriggerModes.MANY_TRIGGERS
        ):
            ext_art_param_dict["detector_params"]["num_triggers"] = n_images
            ext_art_param_dict["detector_params"]["num_images_per_trigger"] = 1
        elif (
            ext_art_param_dict["detector_params"]["trigger_mode"]
            == EigerTriggerModes.ONE_TRIGGER
        ):
            ext_art_param_dict["detector_params"]["num_triggers"] = 1
            ext_art_param_dict["detector_params"]["num_images_per_trigger"] = n_images
        del ext_art_param_dict["detector_params"]["trigger_mode"]

        self.artemis_params = ArtemisParameters(**ext_art_param_dict)

    def __repr__(self):
        r = "[Artemis internal parameters]\n"
        r += repr(self.artemis_params)
        r += f"experiment_params: {self.experiment_params}"
        return r

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
