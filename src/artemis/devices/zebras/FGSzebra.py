from typing import List

from ophyd import Component, Device

from artemis.devices.zebras import zebra_base as zb


class FGSZebra(Device):
    pc: zb.PositionCompare = Component(zb.PositionCompare, "")
    output: zb.ZebraOutputPanel = Component(zb.ZebraOutputPanel, "")
    logic_gates: zb.LogicGateConfigurer = Component(zb.LogicGateConfigurer, "")

    def setup_fast_grid_scan(self):
        self.output.out_pvs[zb.TTL_DETECTOR].put(zb.IN3_TTL)
        self.output.out_pvs[zb.TTL_SHUTTER].put(zb.IN4_TTL)
        self.output.out_pvs[zb.TTL_XSPRESS3].put(zb.DISCONNECT)
        self.output.pulse_1_input.put(zb.DISCONNECT)

    def stage(self) -> List[object]:
        self.setup_fast_grid_scan()
        self.output.disable_fluo_collection()
        return super().stage()

    def unstage(self) -> List[object]:
        self.output.set_shutter_to_manual()
        return super().unstage()
