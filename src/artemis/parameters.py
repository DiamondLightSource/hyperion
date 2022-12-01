import copy
import json
from dataclasses import dataclass, field
from typing import Union

from dataclasses_json import DataClassJsonMixin

from artemis.devices.eiger import DetectorParams
from artemis.devices.fast_grid_scan import GridScanParams
from artemis.devices.rotation_scan import RotationScanParams
from artemis.external_interaction.ispyb.ispyb_dataclass import IspybParams
from artemis.utils import Point3D

SIM_BEAMLINE = "BL03S"
SIM_INSERTION_PREFIX = "SR03S"
ISPYB_PLAN_NAME = "ispyb_readings"
SIM_ZOCALO_ENV = "devrmq"
DEFAULT_EXPERIMENT_TYPE = "grid_scan"

EXPERIMENT_NAMES = ["grid_scan", "rotation_scan"]
EXPERIMENT_TYPE_LIST = [GridScanParams, RotationScanParams]
EXPERIMENT_DICT = dict(zip(EXPERIMENT_NAMES, EXPERIMENT_TYPE_LIST))
EXPERIMENT_TYPES = Union[GridScanParams, RotationScanParams]


def default_field(obj):
    return field(default_factory=lambda: copy.deepcopy(obj))


class WrongExperimentParameterSpecification(Exception):
    pass


@dataclass
class ArtemisParameters(DataClassJsonMixin):
    zocalo_environment: str = SIM_ZOCALO_ENV
    beamline: str = SIM_BEAMLINE
    insertion_prefix: str = SIM_INSERTION_PREFIX
    experiment_type: str = EXPERIMENT_NAMES[0]
    detector_params: DetectorParams = default_field(
        DetectorParams(
            current_energy=100,
            exposure_time=0.1,
            directory="/tmp",
            prefix="file_name",
            run_number=0,
            detector_distance=100.0,
            omega_start=0.0,
            omega_increment=0.0,
            num_images=2000,
            use_roi_mode=False,
            det_dist_to_beam_converter_path="src/artemis/devices/unit_tests/test_lookup_table.txt",
        )
    )
    ispyb_params: IspybParams = default_field(
        IspybParams(
            sample_id=None,
            sample_barcode=None,
            visit_path="",
            pixels_per_micron_x=0.0,
            pixels_per_micron_y=0.0,
            upper_left=Point3D(
                x=None, y=None, z=None
            ),  # gets stored as 2x2D coords - (x, y) and (x, z). Values in pixels
            position=Point3D(x=None, y=None, z=None),
            xtal_snapshots_omega_start=["test_1_y", "test_2_y", "test_3_y"],
            xtal_snapshots_omega_end=["test_1_z", "test_2_z", "test_3_z"],
            transmission=1.0,
            flux=10.0,
            wavelength=0.01,
            beam_size_x=0.1,
            beam_size_y=0.1,
            focal_spot_size_x=0.0,
            focal_spot_size_y=0.0,
            comment="Descriptive comment.",
            resolution=1,
            undulator_gap=1.0,
            synchrotron_mode=None,
            slit_gap_size_x=0.1,
            slit_gap_size_y=0.1,
        )
    )


class FullParameters:
    artemis_params: ArtemisParameters
    experiment_params: EXPERIMENT_TYPES

    def __init__(
        self,
        artemis_parameters: ArtemisParameters = ArtemisParameters(),
        experiment_parameters: GridScanParams = GridScanParams(
            x_steps=4,
            y_steps=200,
            z_steps=61,
            x_step_size=0.1,
            y_step_size=0.1,
            z_step_size=0.1,
            dwell_time=0.2,
            x_start=0.0,
            y1_start=0.0,
            y2_start=0.0,
            z1_start=0.0,
            z2_start=0.0,
        ),
    ) -> None:
        self.artemis_params = copy.deepcopy(artemis_parameters)
        self.experiment_params = copy.deepcopy(experiment_parameters)

    def __eq__(self, other) -> bool:
        if not isinstance(other, FullParameters):
            raise NotImplemented
        if self.artemis_params != other.artemis_params:
            return False
        if self.experiment_params != other.experiment_params:
            return False
        return True

    def to_dict(self) -> dict[str, dict]:
        return {
            "artemis_params": self.artemis_params.to_dict(),
            "experiment_params": self.experiment_params.to_dict(),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, dict_params: dict[str, dict]):
        experiment_type: EXPERIMENT_TYPES = EXPERIMENT_DICT.get(
            dict_params["artemis_params"]["experiment_type"]
        )
        try:
            assert experiment_type is not None
            experiment_params = experiment_type.from_dict(
                dict_params["experiment_params"]
            )
        except Exception:
            raise WrongExperimentParameterSpecification
        return cls(
            ArtemisParameters.from_dict(dict_params["artemis_params"]),
            experiment_params,
        )

    @classmethod
    def from_json(cls, json_params: str):
        dict_params = json.loads(json_params)
        return cls.from_dict(dict_params)

    @classmethod
    def from_file(cls, json_filename: str):
        with open(json_filename) as f:
            return cls.from_json(f.read())
