from enum import Enum

from ophyd import Component, Device, EpicsSignalRO
from ophyd.areadetector.cam import EigerDetectorCam
from ophyd.utils.epics_pvs import set_and_wait

from src.artemis.devices.detector import DetectorParams
from src.artemis.devices.eiger_odin import EigerOdin
from src.artemis.devices.status import await_value


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

    def __init__(
        self, detector_params: DetectorParams, name="Eiger Detector", *args, **kwargs
    ):
        super().__init__(name=name, *args, **kwargs)
        self.detector_params = detector_params
        self.check_detector_variables_set()

    def check_detector_variables_set(self):
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
        self.set_detector_threshold(self.detector_params.current_energy)
        self.set_cam_pvs()
        self.set_odin_pvs()
        self.set_mx_settings_pvs()
        self.set_num_triggers_and_captures()
        self.arm_detector()

    def unstage(self) -> bool:
        self.odin.file_writer.timeout.put(1)
        self.odin.nodes.wait_for_filewriters_to_finish()
        self.disarm_detector()
        self.disable_roi_mode()
        status_ok = self.odin.check_odin_state()
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
        status &= self.odin.file_writer.num_frames_chunks.set(1)
        status &= self.odin.file_writer.num_row_chunks.set(detector_dimensions.height)
        status &= self.odin.file_writer.num_col_chunks.set(detector_dimensions.width)

        status.wait(10)

        if not status.success:
            self.log.error("Failed to switch to ROI mode")

    def set_cam_pvs(self):
        self.cam.acquire_time.put(self.detector_params.exposure_time)
        self.cam.acquire_period.put(self.detector_params.exposure_time)
        self.cam.num_exposures.put(1)
        self.cam.image_mode.put(self.cam.ImageMode.MULTIPLE)
        self.cam.trigger_mode.put(EigerTriggerMode.EXTERNAL_SERIES.value)

    def set_odin_pvs(self):
        self.odin.fan.forward_stream.put(True)
        self.odin.file_writer.id.put(self.detector_params.acquisition_id)
        self.odin.file_writer.file_path.put(self.detector_params.directory)
        self.odin.file_writer.file_prefix.put(self.detector_params.full_filename)
        self.odin.meta.file_name.put(self.detector_params.full_filename)

    def set_mx_settings_pvs(self):
        beam_x_pixels, beam_y_pixels = self.detector_params.get_beam_position_pixels(
            self.detector_params.detector_distance
        )
        self.cam.beam_center_x.put(beam_x_pixels)
        self.cam.beam_center_y.put(beam_y_pixels)
        self.cam.det_distance.put(self.detector_params.detector_distance)
        self.cam.omega_start.put(self.detector_params.omega_start)
        self.cam.omega_incr.put(self.detector_params.omega_increment)

    def set_detector_threshold(self, energy: float) -> bool:
        current_energy = self.cam.photon_energy.get()

        if abs(current_energy - energy) > 0.1:
            self.cam.photon_energy.put(energy)
            return True
        else:
            return False

    def set_num_triggers_and_captures(self):
        self.cam.num_images.put(1)
        self.cam.num_triggers.put(self.detector_params.num_images)
        self.odin.file_writer.num_capture.put(self.detector_params.num_images)

    def wait_for_stale_parameters(self):
        await_value(self.stale_params, 0).wait(self.STALE_PARAMS_TIMEOUT)

    def arm_detector(self):
        self.wait_for_stale_parameters()

        bit_depth = self.bit_depth.get()
        self.odin.file_writer.data_type.put(f"UInt{bit_depth}")

        odin_status = self.odin.file_writer.capture.set(1)
        odin_status &= await_value(self.odin.meta.ready, 1)
        odin_status.wait(10)

        set_and_wait(self.cam.acquire, 1, timeout=10)

        await_value(self.odin.fan.ready, 1).wait(10)

    def disarm_detector(self):
        self.cam.acquire.put(0)
