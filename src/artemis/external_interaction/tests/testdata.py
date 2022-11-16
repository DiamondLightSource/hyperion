from artemis.parameters import ISPYB_PLAN_NAME

DUMMY_TIME_STRING = "1970-01-01 00:00:00"
GOOD_ISPYB_RUN_STATUS = "DataCollection Successful"
BAD_ISPYB_RUN_STATUS = "DataCollection Unsuccessful"
test_start_document = {
    "uid": "d8bee3ee-f614-4e7a-a516-25d6b9e87ef3",
    "time": 1666604299.6149616,
    "versions": {"ophyd": "1.6.4.post76+g0895f9f", "bluesky": "1.8.3"},
    "scan_id": 1,
    "plan_type": "generator",
    "plan_name": "run_gridscan_and_move",
}
test_descriptor_document = {
    "uid": "bd45c2e5-2b85-4280-95d7-a9a15800a78b",
    "run_start": "d8bee3ee-f614-4e7a-a516-25d6b9e87ef3",
    "name": ISPYB_PLAN_NAME,
}
test_event_document = {
    "descriptor": "bd45c2e5-2b85-4280-95d7-a9a15800a78b",
    "time": 1666604299.828203,
    "data": {
        "fgs_slit_gaps_xgap": 0.1234,
        "fgs_slit_gaps_ygap": 0.2345,
        "fgs_synchrotron_machine_status_synchrotron_mode": "test",
        "fgs_undulator_gap": 1.234,
    },
    "timestamps": {"det1": 1666604299.8220396, "det2": 1666604299.8235943},
    "seq_num": 1,
    "uid": "29033ecf-e052-43dd-98af-c7cdd62e8173",
    "filled": {},
}
test_stop_document = {
    "run_start": "d8bee3ee-f614-4e7a-a516-25d6b9e87ef3",
    "time": 1666604300.0310638,
    "uid": "65b2bde5-5740-42d7-9047-e860e06fbe15",
    "exit_status": "success",
    "reason": "",
    "num_events": {"fake_ispyb_params": 1, "primary": 1},
}
test_failed_stop_document = {
    "run_start": "d8bee3ee-f614-4e7a-a516-25d6b9e87ef3",
    "time": 1666604300.0310638,
    "uid": "65b2bde5-5740-42d7-9047-e860e06fbe15",
    "exit_status": "fail",
    "reason": "",
    "num_events": {"fake_ispyb_params": 1, "primary": 1},
}
