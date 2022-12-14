from artemis.devices.det_dim_constants import constants_from_type
from artemis.devices.eiger import DetectorParams
from artemis.external_interaction.ispyb.ispyb_dataclass import IspybParams
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
    detector_params: DetectorParams = DetectorParams(
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
        # detector_size_constants="EIGER2_X_16M_SIZE"
    )

    ispyb_params: IspybParams = IspybParams(
        sample_id=None,
        sample_barcode=None,
        visit_path="",
        pixels_per_micron_x=0.0,
        pixels_per_micron_y=0.0,
        # gets stored as 2x2D coords - (x, y) and (x, z). Values in pixels
        upper_left=Point3D(x=0, y=0, z=0),
        position=Point3D(x=0, y=0, z=0),
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

    def __init__(
        self,
        zocalo_environment: str = SIM_ZOCALO_ENV,
        beamline: str = SIM_BEAMLINE,
        insertion_prefix: str = SIM_INSERTION_PREFIX,
        experiment_type: str = EXPERIMENT_NAMES[0],
        detector_params: DetectorParams = DetectorParams(
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
        ),
        ispyb_params: IspybParams = IspybParams(
            sample_id=None,
            sample_barcode=None,
            visit_path="",
            pixels_per_micron_x=0.0,
            pixels_per_micron_y=0.0,
            # gets stored as 2x2D coords - (x, y) and (x, z). Values in pixels
            upper_left=Point3D(x=0, y=0, z=0),
            position=Point3D(x=0, y=0, z=0),
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
        ),
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

    def __init__(self, external_params: RawParameters = RawParameters()):
        self.artemis_params = ArtemisParameters(
            **external_params.artemis_params.to_dict()
        )
        self.artemis_params.detector_params = DetectorParams(
            **self.artemis_params.detector_params
        )
        self.artemis_params.detector_params.detector_size_constants = (
            constants_from_type(
                self.artemis_params.detector_params.detector_size_constants
            )
        )
        self.artemis_params.ispyb_params = IspybParams(
            **self.artemis_params.ispyb_params
        )
        self.artemis_params.ispyb_params.upper_left = Point3D(
            *self.artemis_params.ispyb_params.upper_left
        )
        self.artemis_params.ispyb_params.position = Point3D(
            *self.artemis_params.ispyb_params.position
        )
        self.experiment_params = EXPERIMENT_DICT[ArtemisParameters.experiment_type](
            **external_params.experiment_params.to_dict()
        )

    def __eq__(self, other) -> bool:
        if not isinstance(other, InternalParameters):
            return NotImplemented
        if self.artemis_params != other.artemis_params:
            return False
        if self.experiment_params != other.experiment_params:
            return False
        return True

    @classmethod
    def from_json(cls, json_data):
        """Convenience method to generate from external parameter JSON blob, uses
        RawParameters.from_json()"""
        return cls(RawParameters.from_json(json_data))
