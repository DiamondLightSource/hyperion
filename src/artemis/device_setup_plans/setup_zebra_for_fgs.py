from artemis.devices.zebra import Zebra

# FROM OUTPUT PANEL
#     def setup_fast_grid_scan(self):
#         self.out_pvs[TTL_DETECTOR].put(IN3_TTL)
#         self.out_pvs[TTL_SHUTTER].put(IN4_TTL)
#         self.out_pvs[TTL_XSPRESS3].put(DISCONNECT)
#         self.pulse_1_input.put(DISCONNECT)
#
#     def disable_fluo_collection(self):
#         self.pulse_1_input.put(DISCONNECT)
#         self.out_pvs[TTL_XSPRESS3].put(DISCONNECT)
#
#     def set_shutter_to_manual(self):
#         self.out_pvs[TTL_DETECTOR].put(PC_PULSE)
#         self.out_pvs[TTL_SHUTTER].put(OR1)

# FROM ZEBRA CLASS
#    def setup_fast_grid_scan(self):
#        self.output.setup_fast_grid_scan()
#
#    def stage(self) -> List[object]:
#        self.setup_fast_grid_scan()
#        self.output.disable_fluo_collection()
#        return super().stage()
#
#    def unstage(self) -> List[object]:
#        self.output.set_shutter_to_manual()
#        return super().unstage()


def setup_zebra_for_fgs(zebra: Zebra):
    pass


def set_zebra_shutter_to_manual(zebra: Zebra):
    pass
