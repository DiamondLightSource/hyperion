from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from functools import cached_property
from pathlib import Path
from typing import TypeVar

from dodal.devices.detector import DetectorParams
from numpy.typing import NDArray
from pydantic import BaseModel, Field
from scanspec.core import AxesPoints
from semver import Version

from hyperion.external_interaction.ispyb.ispyb_dataclass import (
    IspybParams,
)
from hyperion.parameters.constants import CONST

T = TypeVar("T")


class ParameterVersion(Version):
    @classmethod
    def _parse(cls, version):
        if isinstance(version, cls):
            return version
        return cls.parse(version)

    @classmethod
    def __get_validators__(cls):
        """Return a list of validator methods for pydantic models."""
        yield cls._parse

    @classmethod
    def __modify_schema__(cls, field_schema):
        """Inject/mutate the pydantic field schema in-place."""
        field_schema.update(examples=["1.0.2", "2.15.3-alpha", "21.3.15-beta+12345"])


class RotationAxis(str, Enum):
    OMEGA = "omega"
    PHI = "phi"
    CHI = "chi"
    KAPPA = "kappa"


class XyzAxis(str, Enum):
    X = "sam_x"
    Y = "sam_y"
    Z = "sam_z"

    def for_axis(self, x: T, y: T, z: T) -> T:
        match self:
            case XyzAxis.X:
                return x
            case XyzAxis.Y:
                return y
            case XyzAxis.Z:
                return z


class HyperionParameters(BaseModel):
    class Config:
        arbitrary_types_allowed = True
        keep_untouched = (cached_property,)
        use_enum_values = True
        json_encoders = {
            ParameterVersion: lambda pv: str(pv),
        }

    parameter_model_version: ParameterVersion


class DiffractionExperiment(HyperionParameters):
    visit: str = Field(min_length=1)
    file_name: str = Field(min_length=1)
    exposure_time_s: float = Field(gt=0)
    comment: str = ""
    beamline: str = Field(default=CONST.I03.BEAMLINE, pattern=r"BL\d{2}[BIJS]")
    insertion_prefix: str = Field(
        default=CONST.I03.INSERTION_PREFIX, pattern=r"SR\d{2}[BIJS]"
    )
    detector_distance_mm: float | None = Field(default=None, gt=0)
    demand_energy_ev: float | None = Field(default=None, gt=0)
    run_number: float | None = Field(default=None, ge=0)

    @property
    def visit_directory(self) -> Path:
        return Path(CONST.I03.BASE_DATA_DIR) / self.visit

    @cached_property
    @abstractmethod
    def detector_params(self) -> DetectorParams: ...

    @cached_property
    @abstractmethod
    def ispyb_params(self) -> IspybParams:  # Soon to remove
        ...


class WithScan(BaseModel, ABC):
    @cached_property
    @abstractmethod
    def scan_points(self) -> AxesPoints: ...

    @property
    @abstractmethod
    def num_images(self) -> int: ...


class WithSample(BaseModel):
    sample_id: int  # Will be used to work out puck/pin
    _puck: int | None = None
    _pin: int | None = None


class OptionalXyzStarts(BaseModel):
    x_start_um: float | None = None
    y_start_um: float | None = None
    z_start_um: float | None = None


class XyzStarts(BaseModel):
    x_start_um: float
    y_start_um: float
    z_start_um: float


class OptionalGonioAngleStarts(BaseModel):
    omega_start_deg: float | None = None
    phi_start_deg: float | None = None
    chi_start_deg: float | None = None
    kappa_start_deg: float | None = None


class TemporaryIspybExtras(BaseModel):
    # for while we still need ISpyB params - to be removed in #1277 and/or #43
    microns_per_pixel_x: int | None = None
    microns_per_pixel_y: int | None = None
    position: list[float] | NDArray | None = None
    beam_size_x: float | None = None
    beam_size_y: float | None = None
    focal_spot_size_x: float | None = None
    focal_spot_size_y: float | None = None
    resolution: float | None = None
    sample_barcode: str | None = None
    flux: float | None = None
    undulator_gap: float | None = None
    synchrotron_mode: str | None = None
    slit_gap_size_x: float | None = None
    slit_gap_size_y: float | None = None
    xtal_snapshots_omega_start: list[str] | None = None
    xtal_snapshots_omega_end: list[str] | None = None
    ispyb_experiment_type: str | None = None
    upper_left: list[float] | NDArray | None = None
