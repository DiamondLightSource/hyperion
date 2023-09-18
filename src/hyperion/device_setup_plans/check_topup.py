# import bluesky.plan_stubs as bps
from dodal.devices.detector import DetectorParams
from dodal.devices.synchrotron import Synchrotron, SynchrotronMode

ALLOWED_MODES = [SynchrotronMode.USER, SynchrotronMode.SPECIAL]


def check_topup_plan(synchrotron: Synchrotron, params: DetectorParams):
    tot_exposure_time = params.exposure_time * params.full_number_of_images
    time_to_topup = synchrotron.top_up.start_countdown
    print(tot_exposure_time * time_to_topup)

    # if mode precludes gating ie. in decay mode, or not in permitted mode
    # no need to gate
    # if enough time for collection before topup (ttt > tot_exp_t)
    # no need to gate
    # else
    # delay (bps.sleep) till end of topup

    # no need for the part of delay required because exp_tot always shorter
    # for mx
    # pass
