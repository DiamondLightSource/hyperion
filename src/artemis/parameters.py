from dataclasses import dataclass

from dataclasses_json import dataclass_json
from src.artemis.devices.eiger import DetectorParams
from src.artemis.devices.fast_grid_scan import GridScanParams
from src.artemis.ispyb.ispyb_dataclass import IspybParams, Point2D, Point3D

SIM_BEAMLINE = "BL03S"


@dataclass_json
@dataclass
class FullParameters:
    beamline: str = SIM_BEAMLINE
    grid_scan_params: GridScanParams = GridScanParams(
        x_steps=5,
        y_steps=10,
        x_step_size=0.1,
        y_step_size=0.1,
        dwell_time=0.2,
        x_start=0.0,
        y1_start=0.0,
        z1_start=0.0,
    )
    detector_params: DetectorParams = DetectorParams(
        current_energy=100,
        exposure_time=0.1,
        acquisition_id="test",
        directory="/tmp",
        prefix="file_name",
        detector_distance=100.0,
        omega_start=0.0,
        omega_increment=0.1,
        num_images=50,
        use_roi_mode=False,
    )
    ispyb_params: IspybParams = IspybParams(
        sample_id=None,
        visit_path="",
        undulator_gap=1.0,
        pixels_per_micron_x=None,
        pixels_per_micron_y=None,
        upper_left=Point2D(x=None, y=None),
        sample_barcode=None,
        position=Point3D(x=None, y=None, z=None),
        synchrotron_mode=None,
        xtal_snapshots=None,
        run_number=None,
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
