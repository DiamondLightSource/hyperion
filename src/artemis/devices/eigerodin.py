from ophyd import Component, Device, EpicsSignalRO, EpicsSignalWithRBV
from ophyd.status import AndStatus, StatusBase
from ophyd.areadetector.plugins import HDF5Plugin_V22

from status  import await_value

class EigerOdin(Device):
	fan: EigerFan = Component(EigerFan, "OD:FAN:")
	file_writer: OdinFileWriter = Component(OdinFileWriter, "OD:")
	meta: OdinMetaListener = Component(OdinMetaListener, "OD:META")
	nodes: OdinNodes = Component(OdinNodes, "")

	def check_odin_state(self):
		is_initialised, _ = self.check_odin_iniitialised()
		frames_dropped, frames_dropped_details = nodes.check_frames_dropped()
		frames_timed_out, frames_timed_out_details = nodes.check_frames_timed_out()

		if not is_initialised:
			#TODO log message and stop script
		if frames_dropped:
			#TODO log frames_dropped_details
		if frames_timed_out:
			#TODO log frames_timed_out_details

		return is_initialised and not frames_dropped and not frames_timed_out

	def check_odin_initialised(self):
		odin_ready = True
		message = ""

		if not fan.connected.get():
			odin_ready = False
			message += "EigerFan is not connected\n"
		if not fan.on.get():
			odin_ready = False
			message += "EigerFan is not initialised\n"
		if not meta.initialised.get():
			odin_ready = False
			message += "MetaListener is not initialised\n"
		if nodes.get_error_state():
			odin_ready = False
			message += "One or more filewriters is in an error state"
		if not nodes.get_init_state():
			odin_ready = False
			message += "One or more filewriters is not initialised"

		return odin_ready, message

class EigerFan(Device):
	on: EpicsSignalRO = Component(EpicsSignalRO, "ProcessConnected_RBV")
	connected: EpicsSignalRO = Component(EpicsSignalRO, "AllConsumersConnected_RBV")
	ready: EpicsSignalRO = Component(EpicsSignalRO, "StateReady_RBV")
	zmq_addr: EpicsSignalRO = Component(EpicsSignalRO, "EigerAddress_RBV")
	zmq_port: EpicsSignalRO = Component(EpicsSignalRO, "EigerPort_RBV")
	state: EpicsSignalRO = Component(EpicsSignalRO, "State_RBV")
	frames_sent: EpicsSignalRO = Component(EpicsSignalRO, "FramesSent_RBV")
	series: EpicsSignalRO = Component(EpicsSignalRO, "CurrentSeries_RBV")
	offset: EpicsSignalRO = Component(EpicsSignalRO, "CurrentOffset_RBV")
	forward_stream: EpicsSignalWithRBV = Component(EpicsSignalWithRBV, "ForwardStream")

Class OdinMetaListener(Device):
	file_name: EpicsSignalWithRBV = Component(EpicsSignalWithRBV, "FileName")
	initialised: EpicsSignalRO = Component(EpicsSignalRO, "ProcessConnected_RBV")

Class OdinFileWriter(HDF5Plugin_V22):
	timeout: EpicsSignalWithRBV = Component(EpicsSignalWithRBV, "StartTimeout")
	id: EpicsSignalWithRBV = Component(EpicsSignalWithRBV, "AcquisitionID")
	image_height: EpicsSignalWithRBV = Component(EpicsSignalWithRBV, "ImageHeight")
	image_width: EpicsSignalWithRBV = Component(EpicsSignalWithRBV, "ImageWidth")

Class OdinNodes(Device):
	number_of_nodes = 4

	def wait_for_filewriters_to_finish(self):
		for i in range(number_of_nodes):
			node_writing: EpicsSignalRO = Component(EpicsSignalRO, "OD%i:Writing_RBV" % i)
			if node_writing.get():
				await_value(node_writing, 0).wait(10)

	def check_frames_dropped(self):
		frames_dropped = False
		frames_dropped_details = ""
		dropped_frames_filewriter = [0] * number_of_nodes

		for i in range(number_of_nodes):
			node_dropped_frames: EpicsSignalRO = Component(EpicsSignalRO, "OD%i:FramesDropped_RBV" % i)
			dropped_frames_filewriter[i] = node_dropped_frames.get()
			if dropped_frames_filewriter != 0:
				frames_dropped = True
				frames_dropped_details = "Filewriter %d dropped %d frames" % (i, dropped_frames_filewriter[i])

		return frames_dropped, frames_dropped_details

	def check_frames_timed_out(self):
		frames_timed_out = False
                frames_timed_out_details = ""
                timed_out_frames_filewriter = [0] * number_of_nodes 

                for i in range(number_of_nodes):
                        node_timed_out_frames: EpicsSignalRO = Component(EpicsSignalRO, "OD%i:FramesTimedOut_RBV" % i)
                        timed_out_frames_filewriter[i] = node_timed_out_frames.get()
                        if timed_out_frames_filewriter !=	0:
                                frames_timed_out = True
                                frames_timed_out_details = "Filewriter %d timed out %d frames" % (i, timed_out_frames_filewriter[i])

                return frames_timed_out, frames_timed_out_details

	def get_error_state(self):
		for i in range(number_of_nodes):
			node_error_status: EpicsSignalRO = Component(EpicsSignalRO, "OD%i:FPErrorState_RBV" % i)
			if node_error_status.get():
				return True
		return False

	def get_init_state(self):
		for i in range(number_of_nodes):
                        node_fr_init: EpicsSignalRO = Component(EpicsSignalRO, "OD%i:FPProcessConnected_RBV" % i)
			node_fp_init: EpicsSignalRO = Component(EpicsSignalRO, "OD%i:FRProcessConnected_RBV" % i)
                        if not (node_fr_init.get() and node_fp_init.get()):
                                return False
                return True

