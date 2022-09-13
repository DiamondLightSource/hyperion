from typing import List, Tuple

from ophyd import Component, Device, EpicsSignal, EpicsSignalRO, EpicsSignalWithRBV
from ophyd.areadetector.plugins import HDF5Plugin_V22

from artemis.devices.status import await_value


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


class OdinMetaListener(Device):
    initialised: EpicsSignalRO = Component(EpicsSignalRO, "ProcessConnected_RBV")
    ready: EpicsSignalRO = Component(EpicsSignalRO, "Writing_RBV")
    file_name: EpicsSignal = Component(EpicsSignal, "FileName")


class OdinFileWriter(HDF5Plugin_V22):
    timeout: EpicsSignal = Component(EpicsSignal, "StartTimeout")
    id: EpicsSignalWithRBV = Component(EpicsSignalWithRBV, "AcquisitionID")
    image_height: EpicsSignalWithRBV = Component(EpicsSignalWithRBV, "ImageHeight")
    image_width: EpicsSignalWithRBV = Component(EpicsSignalWithRBV, "ImageWidth")


class OdinNode(Device):
    writing: EpicsSignalRO = Component(EpicsSignalRO, "Writing_RBV")
    frames_dropped: EpicsSignalRO = Component(EpicsSignalRO, "FramesDropped_RBV")
    frames_timed_out: EpicsSignalRO = Component(EpicsSignalRO, "FramesTimedOut_RBV")
    error_status: EpicsSignalRO = Component(EpicsSignalRO, "FPErrorState_RBV")
    fp_initialised: EpicsSignalRO = Component(EpicsSignalRO, "FPProcessConnected_RBV")
    fr_initialised: EpicsSignalRO = Component(EpicsSignalRO, "FRProcessConnected_RBV")
    clear_errors: EpicsSignal = Component(EpicsSignal, "FPClearErrors")
    error_message: EpicsSignalRO = Component(EpicsSignalRO, "FPErrorMessage_RBV")


class OdinNodesStatus(Device):
    node_0: OdinNode = Component(OdinNode, "OD1:")
    node_1: OdinNode = Component(OdinNode, "OD2:")
    node_2: OdinNode = Component(OdinNode, "OD3:")
    node_3: OdinNode = Component(OdinNode, "OD4:")

    @property
    def nodes(self) -> List[OdinNode]:
        return [self.node_0, self.node_1, self.node_2, self.node_3]

    def wait_for_filewriters_to_finish(self):
        for node_number, node_pv in enumerate(self.nodes):
            if node_pv.writing.get():
                await_value(node_pv.writing, 0).wait(30)

    def check_node_frames_from_attr(
        self, node_get_func, error_message_verb: str
    ) -> Tuple[bool, str]:
        nodes_frames_values = [0] * len(self.nodes)
        frames_details = []
        for node_number, node_pv in enumerate(self.nodes):
            nodes_frames_values[node_number] = node_get_func(node_pv)
            error_message = f"Filewriter {node_number} {error_message_verb} \
                    {nodes_frames_values[node_number]} frames"
            frames_details.append(error_message)
        bad_frames = any(v != 0 for v in nodes_frames_values)
        return bad_frames, "\n".join(frames_details)

    def check_frames_timed_out(self) -> Tuple[bool, str]:
        return self.check_node_frames_from_attr(
            lambda node: node.frames_timed_out.get(), "timed out"
        )

    def check_frames_dropped(self) -> Tuple[bool, str]:
        return self.check_node_frames_from_attr(
            lambda node: node.frames_dropped.get(), "dropped"
        )

    def get_error_state(self) -> Tuple[bool, str]:
        is_error = []
        error_messages = []
        for node_number, node_pv in enumerate(self.nodes):
            is_error.append(node_pv.error_status.get())
            if is_error[node_number]:
                error_messages.append(
                    f"Filewriter {node_number} is in an error state with error message\
                     - {node_pv.error_message.get()}"
                )
        return any(is_error), "\n".join(error_messages)

    def get_init_state(self) -> bool:
        is_initialised = []
        for node_number, node_pv in enumerate(self.nodes):
            is_initialised.append(node_pv.fr_initialised.get())
            is_initialised.append(node_pv.fp_initialised.get())
        return all(is_initialised)

    def clear_odin_errors(self):
        for node_number, node_pv in enumerate(self.nodes):
            error_message = node_pv.error_message.get()
            if len(error_message) != 0:
                self.log.info(f"Clearing odin errors from node {node_number}")
                node_pv.clear_errors.put(1)


class EigerOdin(Device):
    fan: EigerFan = Component(EigerFan, "OD:FAN:")
    file_writer: OdinFileWriter = Component(OdinFileWriter, "OD:")
    meta: OdinMetaListener = Component(OdinMetaListener, "OD:META:")
    nodes: OdinNodesStatus = Component(OdinNodesStatus, "")

    def check_odin_state(self) -> bool:
        is_initialised, error_message = self.check_odin_initialised()
        frames_dropped, frames_dropped_details = self.nodes.check_frames_dropped()
        frames_timed_out, frames_timed_out_details = self.nodes.check_frames_timed_out()

        if not is_initialised:
            raise Exception(error_message)
        if frames_dropped:
            self.log.error(f"Frames dropped: {frames_dropped_details}")
        if frames_timed_out:
            self.log.error(f"Frames timed out: {frames_timed_out_details}")

        return is_initialised and not frames_dropped and not frames_timed_out

    def check_odin_initialised(self) -> Tuple[bool, str]:
        is_error_state, error_messages = self.nodes.get_error_state()
        to_check = [
            (not self.fan.connected.get(), "EigerFan is not connected"),
            (not self.fan.on.get(), "EigerFan is not initialised"),
            (not self.meta.initialised.get(), "MetaListener is not initialised"),
            (is_error_state, error_messages),
            (
                not self.nodes.get_init_state(),
                "One or more filewriters is not initialised",
            ),
        ]

        errors = [message for check_result, message in to_check if check_result]

        return not errors, "\n".join(errors)
