"""
Define beamline parameters for I03, Eiger detector and give an example of writing a gridscan.
"""
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple

import h5py
import numpy as np
from nexgen.nxs_write import calculate_scan_from_scanspec
from nexgen.nxs_write.NexusWriter import call_writers
from nexgen.nxs_write.NXclassWriters import write_NXentry
from nexgen.tools.VDS_tools import image_vds_writer
from scanspec.specs import Line, Spec
from src.artemis.devices.detector import DetectorParams
from src.artemis.devices.fast_grid_scan import GridScanParams
from src.artemis.ispyb.ispyb_dataclass import IspybParams
from src.artemis.parameters import FullParameters

source = {
    "name": "Diamond Light Source",
    "short_name": "DLS",
    "type": "Synchrotron X-ray Source",
    "beamline_name": "I03",
}

dset_links = [
    [
        "pixel_mask",
        "pixel_mask_applied",
        "flatfield",
        "flatfield_applied",
        "threshold_energy",
        "bit_depth_readout",
        "detector_readout_time",
        "serial_number",
    ],
    ["software_version"],
]

module = {
    "fast_axis": [-1.0, 0.0, 0.0],
    "slow_axis": [0.0, -1.0, 0.0],
    "module_offset": "1",
}


def create_goniometer_axes(detector_params: DetectorParams) -> Dict:
    """Create the data for the goniometer.

    Args:
        detector_params (DetectorParams): Information about the detector.

    Returns:
        Dict: A dictionary describing the gonio for nexgen
    """
    # fmt: off
    return {
        "axes": ["omega", "sam_z", "sam_y", "sam_x", "chi", "phi"],
        "depends": [".", "omega", "sam_z", "sam_y", "sam_x", "chi"],
        "vectors": [
            -1, 0.0, 0.0,
            0.0, 0.0, 1.0,
            0.0, 1.0, 0.0,
            1.0, 0.0, 0.0,
            0.006, -0.0264, 0.9996,
            -1, -0.0025, -0.0056,
        ],
        "types": [
            "rotation",
            "translation",
            "translation",
            "translation",
            "rotation",
            "rotation",
        ],
        "units": ["deg", "mm", "mm", "mm", "deg", "deg"],
        "offsets": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        "starts": [detector_params.omega_start, 0.0, None, None, 0.0, 0.0],
        "ends": [detector_params.omega_end] + [0.0] * 5,
        "increments": [detector_params.omega_increment] + [0.0] * 5,
    }
    # fmt: on


def create_detector_parameters(detector_params: DetectorParams) -> Dict:
    """Returns the detector information in a format that nexgen wants.

    Args:
        detector_params (DetectorParams): The detector params as Artemis stores them.

    Returns:
        Dict: The dictionary for nexgen to write.
    """
    detector_pixels = detector_params.get_detector_size_pizels()
    return {
        "mode": "images",
        "description": "Eiger 16M",
        "detector_type": "Pixel",
        "sensor_material": "Silicon",
        "sensor_thickness": "4.5E-4",
        "overload": 46051,
        "underload": -1,  # Not sure of this
        "pixel_size": ["0.075mm", "0.075mm"],
        "flatfield": "flatfield",
        "flatfield_applied": "_dectris/flatfield_correction_applied",
        "pixel_mask": "mask",
        "pixel_mask_applied": "_dectris/pixel_mask_applied",
        "image_size": [detector_pixels.width, detector_pixels.height],  # (fast, slow)
        "axes": ["det_z"],
        "depends": ["."],
        "vectors": [0.0, 0.0, 1.0],
        "types": ["translation"],
        "units": ["mm"],
        "starts": [detector_params.detector_distance],
        "ends": [detector_params.detector_distance],
        "increments": [0.0],
        "bit_depth_readout": "_dectris/bit_depth_readout",
        "detector_readout_time": "_dectris/detector_readout_time",
        "threshold_energy": "_dectris/threshold_energy",
        "software_version": "_dectris/software_version",
        "serial_number": "_dectris/detector_number",
        "beam_center": detector_params.get_beam_position_pixels(
            detector_params.detector_distance
        ),
        "exposure_time": detector_params.exposure_time,
    }


def create_beam_and_attenuator_parameters(
    ispyb_params: IspybParams,
) -> Tuple[Dict, Dict]:
    """Create beam and attenuator dictionaries that nexgen can understand.

    Args:
        ispyb_params (IspybParams): An IspybParams object holding all required data.

    Returns:
        Tuple[Dict, Dict]: Tuple of dictionaries describing the beam and attenuator parameters respectively
    """
    return (
        {"wavelength": ispyb_params.wavelength, "flux": ispyb_params.flux},
        {"transmission": ispyb_params.transmission},
    )


def create_scan_spec(grid_scan_params: GridScanParams) -> Spec:
    """Create a scan spec from the grid scan parameters.

    Args:
        grid_scan_params (GridScanParams): The grid scan parameters.

    Returns:
        Spec: A scanspec for nexgen
    """
    y_line = Line(
        "sam_y",
        grid_scan_params.y1_start,
        grid_scan_params.y_end,
        grid_scan_params.y_steps
        + 1,  # 1 more as we take an image on the first step as well as the last
    )
    x_line = Line(
        "sam_x",
        grid_scan_params.x_start,
        grid_scan_params.x_end,
        grid_scan_params.x_steps + 1,
    )
    return y_line * ~x_line


class NexusWriter:
    def __init__(self, parameters: FullParameters) -> None:
        self.detector = create_detector_parameters(parameters.detector_params)
        self.goniometer = create_goniometer_axes(parameters.detector_params)
        self.beam, self.attenuator = create_beam_and_attenuator_parameters(
            parameters.ispyb_params
        )
        self.scan_spec = create_scan_spec(parameters.grid_scan_params)
        self.directory = Path(parameters.detector_params.directory)
        self.filename = parameters.detector_params.full_filename
        self.num_of_images = parameters.detector_params.num_images
        self.nexus_file = self.directory / f"{self.filename}.nxs"
        self.master_file = self.directory / f"{self.filename}_master.h5"

    def _get_current_time(self):
        return datetime.utcfromtimestamp(time.time()).strftime(r"%Y-%m-%dT%H:%M:%SZ")

    def __enter__(self):
        """
        Creates a nexus file based on the parameters supplied when this obect was initialised.
        """
        start_time = self._get_current_time()

        scan_range = calculate_scan_from_scanspec(self.scan_spec)

        image_data = [self.directory / f"{self.filename}_000001.h5"]
        metafile = self.directory / f"{self.filename}_meta.h5"

        for filename in [self.nexus_file, self.master_file]:
            with h5py.File(filename, "x") as nxsfile:
                nxentry = write_NXentry(nxsfile)

                nxentry.create_dataset("start_time", data=np.string_(start_time))

                call_writers(
                    nxsfile,
                    image_data,
                    "mcstas",
                    scan_range,
                    ("images", self.num_of_images),
                    self.goniometer,
                    self.detector,
                    module,
                    source,
                    self.beam,
                    self.attenuator,
                    metafile=metafile,
                    link_list=dset_links,
                )

                image_vds_writer(
                    nxsfile,
                    (
                        self.num_of_images,
                        self.detector["image_size"][1],
                        self.detector["image_size"][0],
                    ),
                )

    def __exit__(self, *_):
        for filename in [self.nexus_file, self.master_file]:
            with h5py.File(filename, "r+") as nxsfile:
                nxsfile["entry"].create_dataset(
                    "end_time", data=np.string_(self._get_current_time())
                )
