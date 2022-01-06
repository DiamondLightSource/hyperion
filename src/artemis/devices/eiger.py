from ophyd import (
	Component,
	DetectorBase,
	Device,
	EpicsSignalRO,
	EpcisSignalWithRBV,
	SingleTrigger,
	StatusBase
)

from ophyd.areadetector.cam import EigerDetectorCam
from ophyd.status import AndStatus

from eigerodin import EigerOdin
import DetDimConstants
import DetDistToBeamConverter
from status import await_value

class EigerManualInterface(Device):
	manual_trigger: EpicsSignalWithRBV = Component(EpicsSignalWithRBV, "ManualTrigger")
	trigger_now: EpicsSignal = Component(EpicsSignal, "Trigger")
	num_triggers: EpicsSignalWithRBV = Component(EpicsSignalWithRBV, "NumTriggers")

class EigerDetector(Device):
	cam: EigerDetectorCam = Component(EigerDetectorCam, "CAM:")
	odin: EigerOdin = Component(EigerOdin, "")
	manual: EigerManualInterface = Component(EigerManualInterface, "CAM:")

	stale_params: EpicsSingalRO = Component(EpicsSignalRO, "CAM:StaleParameters_RBV")
	bit_depth: EpicsSignalRO = Component(EpicsSignalRO, "CAM:BitDepthImage_RBV")

	def __init__(self, detector_size_constants, use_roi_mode):
		self.detector_size = detector_size_constants
		self.use_roi_mode = use_roi_mode

	def stage(self):
		if self.use_roi_mode:
			self.enable_roi_mode()
		self.set_detector_threshold(current_energy)
		self.set_cam_pvs()
		self.set_odin_pvs()
		self.set_mx_settings_pvs()
		self.arm_detector()

	def unstage(self):
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

	def change_roi_mode(self, enable):
		detector_dimensions = self.detector_size.roi_size_pixels if enable else self.detector_size.detector_size_pixels
		self.cam.roi_mode.put(1 if enable else 0)
		self.odin.file_writer.image_height.put(detector_dimensions.get_height())
		self.odin.file_writer.image_width.put(detector_dimensions.get_width())
		self.odin.file_writer.num_frames_chunks.put(1)
		self.odin.file_writer.num_col_chunks.put(detector_dimensions.get_width())
		self.odin.file_writer.num_row_chunks.put(detector_dimensions.get_height())

	def set_cam_pvs(self):
		self.cam.acquire_time.put(exposure_time)
		self.cam.acquire_period.put(exposure_time)
		self.cam.num_exposures.put(1)
		self.cam.image_mode.put(self.ImageMode.MULTIPLE)
		self.cam.trigger_mode.put("External Series")

	def set_odin_pvs(self):
		self.odin.fan.forward_stream.put(True)
		self.odin.file_writer.id.put(acquisition_id)
		self.odin.file_writer.file_path.put(directory)
		self.odin.file_writer.file_name.put(prefix)
		self.odin.meta.file_name.put(prefix)

	def set_mx_settings_pvs(self):
		beam_x_pixels, beam_y_pixels = self.get_beam_position_pixels(detector_distance)
		self.cam.beam_center_x.put(beam_x_pixels)
		self.cam.beam_center_y.put(beam_y_pixels)
		self.cam.det_distance.put(det_distance)
		self.cam.omega_start.put(omega_start)
		self.cam.omega_incr.put(omega_inr)

	def get_beam_position_pixels(self, detector_distance):
		x_size = self.detector_size.detector_size_pixels.get_width()
		y_size = self.detector_size.decteor_size_pixels.get_height()
		beam_x = DetDistToBeamConverter.get_beam_x_pixels(detector_distance, x_size, self.detector_size.detector_dimension.get_width())
		beam_y = DetDistToBeamConverter.get_beam_y_pixels(detector_distance, y_size, self.detector_size.detector_dimension.get_height())

		offset_x = (x_size - self.detector_size.roi_size_pixels.get_width())
		offset_y = (y_size - self.detector_size.roi_size_pixels.get_height())

		return beam_x - offset_x, beam_y - offset_y

	def set_detector_threshold(self, energy):
		current_energy = self.cam.photon_energy.get()
		
		if abs(current_energy - energy) > 0.1:
			self.cam.photon_energy.put(energy)
			return True
		else:
			return False

	def wait_for_stale_parameters(self):
		await_value(self.stale_params, 0).wait(10)

	def arm_detector(self):
		self.wait_for_stale_parameters()

		bit_depth = self.bit_depth.get()
		self.odin.file_writer.data_type.put(bit_depth)
	
		self.odin.file_writer.capture.put(1)
		await_value(self.odin.file_writer.capture, 1).wait(10)

		self.cam.acquire.put(1)
		await_value(self.cam.acquire, 1).wait(10)

		await_value(self.odin.fan.ready, 1).wait(10)

	def disarm_detector(self):
		self.cam.acquire.put(0)
