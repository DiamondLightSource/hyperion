from ophyd import Component, Device, EpicsSignal

# option to use tikit device instead of the real synchrotron PV's
USE_TIKIT = False


class SynchrotoronMachineStatus(Device):
    synchrotron_mode: EpicsSignal = Component(EpicsSignal, "MODE", string=True)
    beam_dump_countdown: EpicsSignal = Component(EpicsSignal, "USERCOUNTDN")
    ring_energy: EpicsSignal = Component(EpicsSignal, "BEAMENERGY")


class SynchrotronTopUp(Device):
    topup_start_countdown: EpicsSignal = Component(EpicsSignal, "COUNTDOWN")
    topup_end_countdown: EpicsSignal = Component(EpicsSignal, "ENDCOUNTDN")


class Synchrotron(Device):
    machine_status_PV = "BL03S-CS-CS-MSTAT-01:" if USE_TIKIT else "CS-CS-MSTAT-01:"
    top_up_PV = "BL03S-SR-CS-FILL-01:" if USE_TIKIT else "SR-CS-FILL-01:"
    ring_current_PV = (
        "BL03S-SR-DI-DCCT-01:SIGNAL" if USE_TIKIT else "SR-DI-DCCT-01:SIGNAL"
    )

    machine_status: SynchrotoronMachineStatus = Component(
        SynchrotoronMachineStatus, machine_status_PV
    )
    top_up: SynchrotronTopUp = Component(SynchrotronTopUp, top_up_PV)
    ring_current: EpicsSignal = Component(EpicsSignal, ring_current_PV)
