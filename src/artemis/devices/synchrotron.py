from ophyd import Component, Device, EpicsSignal


class SynchrotoronMachineStatus(Device):
    synchrotron_mode: EpicsSignal = Component(
        EpicsSignal, "CS-CS-MSTAT-01:MODE", string=True
    )
    ring_energy: EpicsSignal = Component(EpicsSignal, "CS-CS-MSTAT-01:BEAMENERGY")
    beam_dump_countdown: EpicsSignal = Component(
        EpicsSignal, "CS-CS-MSTAT-01:USERCOUNTDN"
    )


class SynchrotronTopUp(Device):
    topup_start_countdown: EpicsSignal = Component(
        EpicsSignal, "SR-CS-FILL-01:COUNTDOWN"
    )
    topup_end_countdown: EpicsSignal = Component(
        EpicsSignal, "SR-CS-FILL-01:ENDCOUNTDN"
    )


class Synchrotron(Device):

    machine_status: SynchrotoronMachineStatus = Component(SynchrotoronMachineStatus, "")
    top_up: SynchrotronTopUp = Component(SynchrotronTopUp, "")

    ring_current: EpicsSignal = Component(EpicsSignal, "SR-DI-DCCT-01:SIGNAL")
