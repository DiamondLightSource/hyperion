from __future__ import annotations

import datetime
import json
from abc import abstractmethod
from pathlib import Path
from typing import TypeVar

from dodal.devices.detector import (
    TriggerMode,
)
from mx_bluesky.parameters import DiffractionExperiment, ParameterVersion, WithSample
from numpy.typing import NDArray
from pydantic import BaseModel, Extra, Field, validator

from hyperion.external_interaction.config_server import FeatureFlags
from hyperion.external_interaction.ispyb.ispyb_dataclass import (
    IspybParams,
)
from hyperion.parameters.constants import CONST

T = TypeVar("T")


PARAMETER_VERSION = ParameterVersion.parse("5.0.0")


class HyperionParameters(BaseModel):
    class Config:
        arbitrary_types_allowed = True
        extra = Extra.forbid
        json_encoders = {
            ParameterVersion: lambda pv: str(pv),
            NDArray: lambda a: a.tolist(),
        }

    def __hash__(self) -> int:
        return self.json().__hash__()

    features: FeatureFlags = Field(default=FeatureFlags())
    parameter_model_version: ParameterVersion

    @validator("parameter_model_version")
    def _validate_version(cls, version: ParameterVersion):
        assert (
            version >= ParameterVersion(major=PARAMETER_VERSION.major)
        ), f"Parameter version too old! This version of hyperion uses {PARAMETER_VERSION}"
        assert (
            version <= ParameterVersion(major=PARAMETER_VERSION.major + 1)
        ), f"Parameter version too new! This version of hyperion uses {PARAMETER_VERSION}"
        return version

    @classmethod
    def from_json(cls, input: str | None, *, allow_extras: bool = False):
        assert input is not None
        if allow_extras:
            cls.Config.extra = Extra.ignore
        params = cls(**json.loads(input))
        cls.Config.extra = Extra.forbid
        return params


class HyperionDiffractionExperiment(DiffractionExperiment, HyperionParameters):
    """For all experiments which use beam"""

    beamline: str = Field(default=CONST.I03.BEAMLINE, pattern=r"BL\d{2}[BIJS]")
    insertion_prefix: str = Field(
        default=CONST.I03.INSERTION_PREFIX, pattern=r"SR\d{2}[BIJS]"
    )
    det_dist_to_beam_converter_path: str = Field(
        default=CONST.PARAM.DETECTOR.BEAM_XY_LUT_PATH
    )
    zocalo_environment: str = Field(default=CONST.ZOCALO_ENV)
    trigger_mode: TriggerMode = Field(default=TriggerMode.FREE_RUN)

    @property
    def visit_directory(self) -> Path:
        return (
            Path(CONST.I03.BASE_DATA_DIR) / str(datetime.date.today().year) / self.visit
        )

    @property
    @abstractmethod
    def ispyb_params(self) -> IspybParams:  # Soon to remove
        ...


class DiffractionExperimentWithSample(HyperionDiffractionExperiment, WithSample): ...


class TemporaryIspybExtras(BaseModel):
    # for while we still need ISpyB params - to be removed in #1277 and/or #43
    class Config:
        arbitrary_types_allowed = True
        extra = Extra.forbid

    xtal_snapshots_omega_start: list[str] | None = None
