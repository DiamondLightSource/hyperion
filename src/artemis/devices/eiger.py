from enum import Enum

from ophyd import Component, Device, EpicsSignalRO, StatusBase
from ophyd.areadetector.cam import EigerDetectorCam
from ophyd.status import Status

from artemis.devices.detector import DetectorParams
from artemis.devices.eiger_odin import EigerOdin
from artemis.devices.status import await_value
from artemis.log import LOGGER


class EigerTriggerMode(Enum):
    INTERNAL_SERIES = 0
    INTERNAL_ENABLE = 1
    EXTERNAL_SERIES = 2
    EXTERNAL_ENABLE = 3


class EigerDetector(Device):
    cam: EigerDetectorCam = Component(EigerDetectorCam, "CAM:")
    odin: EigerOdin = Component(EigerOdin, "")

    stale_params: EpicsSignalRO = Component(EpicsSignalRO, "CAM:StaleParameters_RBV")
    bit_depth: EpicsSignalRO = Component(EpicsSignalRO, "CAM:BitDepthImage_RBV")

    STALE_PARAMS_TIMEOUT = 60

    filewriters_finished: StatusBase

    detector_params = None

    def set_detector_parameters(self, detector_params: DetectorParams):
        self.detector_params = detector_params
        if self.detector_params is None:
            raise Exception("Parameters for scan must be specified")

        to_check = [
            (
                self.detector_params.detector_size_constants is None,
                "Detector Size must be set",
            ),
            (
                self.detector_params.beam_xy_converter is None,
                "Beam converter must be set",
            ),
        ]

        errors = [message for check_result, message in to_check if check_result]

        if errors:
            raise Exception("\n".join(errors))

    def stage(self):
        self.odin.nodes.clear_odin_errors()
        status_ok, error_message = self.odin.check_odin_initialised()
        if not status_ok:
            raise Exception(f"Odin not initialised: {error_message}")
        if self.detector_params.use_roi_mode:
            self.enable_roi_mode()
        status = self.set_detector_threshold(self.detector_params.current_energy)
        status &= self.set_cam_pvs()
        status &= self.set_odin_pvs()
        status &= self.set_mx_settings_pvs()
        status &= self.set_num_triggers_and_captures()

        LOGGER.info("Waiting on parameter callbacks")
        status.wait(self.STALE_PARAMS_TIMEOUT)

        self.arm_detector()

    def unstage(self) -> bool:
        self.odin.file_writer.start_timeout.put(1)
        self.filewriters_finished.wait(30)
        self.disarm_detector()
        status_ok = self.odin.check_odin_state()
        self.disable_roi_mode()
        return status_ok

    def enable_roi_mode(self):
        self.change_roi_mode(True)

    def disable_roi_mode(self):
        self.change_roi_mode(False)

    def change_roi_mode(self, enable: bool):
        detector_dimensions = (
            self.detector_params.detector_size_constants.roi_size_pixels
            if enable
            else self.detector_params.detector_size_constants.det_size_pixels
        )

        status = self.cam.roi_mode.set(1 if enable else 0)
        status &= self.odin.file_writer.image_height.set(detector_dimensions.height)
        status &= self.odin.file_writer.image_width.set(detector_dimensions.width)
        status &= self.odin.file_writer.num_row_chunks.set(detector_dimensions.height)
        status &= self.odin.file_writer.num_col_chunks.set(detector_dimensions.width)

        status.wait(10)

        if not status.success:
            self.log.error("Failed to switch to ROI mode")

    def set_cam_pvs(self) -> Status:
        status = self.cam.acquire_time.set(self.detector_params.exposure_time)
        status &= self.cam.acquire_period.set(self.detector_params.exposure_time)
        status &= self.cam.num_exposures.set(1)
        status &= self.cam.image_mode.set(self.cam.ImageMode.MULTIPLE)
        status &= self.cam.trigger_mode.set(EigerTriggerMode.EXTERNAL_SERIES.value)
        return status

    def set_odin_pvs(self):
        self.odin.file_writer.num_frames_chunks.set(1).wait(10)

        file_prefix = self.detector_params.full_filename

        odin_status = self.odin.file_writer.file_path.set(
            self.detector_params.directory
        )
        odin_status &= self.odin.file_writer.file_name.set(file_prefix)

        odin_status &= await_value(self.odin.meta.file_name, file_prefix)
        odin_status &= await_value(self.odin.file_writer.id, file_prefix)

        return odin_status

    def set_mx_settings_pvs(self) -> Status:
        beam_x_pixels, beam_y_pixels = self.detector_params.get_beam_position_pixels(
            self.detector_params.detector_distance
        )
        status = self.cam.beam_center_x.set(beam_x_pixels)
        status &= self.cam.beam_center_y.set(beam_y_pixels)
        status &= self.cam.det_distance.set(self.detector_params.detector_distance)
        status &= self.cam.omega_start.set(self.detector_params.omega_start)
        status &= self.cam.omega_incr.set(self.detector_params.omega_increment)
        return status

    def set_detector_threshold(self, energy: float, tolerance: float = 0.1) -> Status:
        """Ensures the energy threshold on the detector is set to the specified energy (in eV),
        within the specified tolerance.
        Args:
            energy (float): The energy to set (in eV)
            tolerance (float, optional): If the energy is already set to within
                this tolerance it is not set again. Defaults to 0.1eV.
        Returns:
            status object that is Done when the threshold has been set correctly
        """
        current_energy = self.cam.photon_energy.get()

        if abs(current_energy - energy) > tolerance:
            return self.cam.photon_energy.set(energy)
        else:
            status = Status(self)
            status.set_finished()
            return status

    def set_num_triggers_and_captures(self) -> Status:
        status = self.cam.num_images.set(1)
        status &= self.cam.num_triggers.set(self.detector_params.num_images)
        status &= self.odin.file_writer.num_capture.set(self.detector_params.num_images)
        return status

    def wait_for_stale_parameters(self):
        await_value(self.stale_params, 0).wait(self.STALE_PARAMS_TIMEOUT)

    def forward_bit_depth_to_filewriter(self):
        bit_depth = self.bit_depth.get()
        self.odin.file_writer.data_type.put(f"UInt{bit_depth}")

    def arm_detector(self):
        LOGGER.info("Waiting on stale parameters to go low")
        self.wait_for_stale_parameters()

        self.forward_bit_depth_to_filewriter()

        odin_status = self.odin.file_writer.capture.set(1)
        odin_status &= await_value(self.odin.meta.ready, 1)
        odin_status.wait(10)

        LOGGER.info("Setting aquire")
        self.cam.acquire.set(1).wait(timeout=10)

        self.filewriters_finished = self.odin.create_finished_status()

        await_value(self.odin.fan.ready, 1).wait(10)

    def disarm_detector(self):
        self.cam.acquire.put(0)
