from ophyd import Component, Device, EpicsSignal


class SynchrotoronMachineStatus(Device):
    synchrotron_mode: EpicsSignal = Component(EpicsSignal, "MODE", string=True)
    beam_dump_countdown: EpicsSignal = Component(EpicsSignal, "USERCOUNTDN")
    ring_energy: EpicsSignal = Component(EpicsSignal, "BEAMENERGY")


class SynchrotronTopUp(Device):
    topup_start_countdown: EpicsSignal = Component(EpicsSignal, "COUNTDOWN")
    topup_end_countdown: EpicsSignal = Component(EpicsSignal, "ENDCOUNTDN")


class Synchrotron(Device):

    machine_status: SynchrotoronMachineStatus = Component(
        SynchrotoronMachineStatus, "CS-CS-MSTAT-01:"
    )
    top_up: SynchrotronTopUp = Component(SynchrotronTopUp, "SR-CS-FILL-01:")

    ring_current: EpicsSignal = Component(EpicsSignal, "SR-DI-DCCT-01:SIGNAL")
