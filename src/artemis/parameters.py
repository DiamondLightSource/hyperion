import copy
from dataclasses import dataclass, field

from dataclasses_json import dataclass_json

from artemis.devices.eiger import DetectorParams
from artemis.devices.fast_grid_scan import GridScanParams
from artemis.ispyb.ispyb_dataclass import IspybParams
from artemis.utils import Point3D

SIM_BEAMLINE = "BL03S"
SIM_INSERTION_PREFIX = "SR03S"


def default_field(obj):
    return field(default_factory=lambda: copy.deepcopy(obj))


@dataclass_json
@dataclass
class FullParameters:
    beamline: str = SIM_BEAMLINE
    insertion_prefix: str = SIM_INSERTION_PREFIX
    grid_scan_params: GridScanParams = default_field(
        GridScanParams(
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
        )
    )
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
            num_images=300,
            use_roi_mode=False,
            det_dist_to_beam_converter_path="src/artemis/devices/unit_tests/test_lookup_table.txt",
        )
    )
    ispyb_params: IspybParams = default_field(
        IspybParams(
            sample_id=None,
            visit_path="",
            undulator_gap=1.0,
            pixels_per_micron_x=None,
            pixels_per_micron_y=None,
            upper_left=Point3D(
                x=None, y=None, z=None
            ),  # gets stored as 2x2D coords - (x, y) and (x, z). Values in pixels
            sample_barcode=None,
            position=Point3D(x=None, y=None, z=None),
            synchrotron_mode=None,
            xtal_snapshots_omega_start=["test_1_y", "test_2_y", "test_3_y"],
            xtal_snapshots_omega_end=["test_1_z", "test_2_z", "test_3_z"],
            transmission=1.0,
            flux=10.0,
            wavelength=0.01,
            beam_size_x=None,
            beam_size_y=None,
            slit_gap_size_x=None,
            slit_gap_size_y=None,
            focal_spot_size_x=None,
            focal_spot_size_y=None,
            comment="",
            resolution=None,
        )
    )
