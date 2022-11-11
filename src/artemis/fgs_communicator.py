import os
import time

from bluesky.callbacks import CallbackBase

import artemis.log
from artemis.ispyb.store_in_ispyb import StoreInIspyb2D, StoreInIspyb3D
from artemis.nexus_writing.write_nexus import (
    NexusWriter,
    create_parameters_for_first_file,
    create_parameters_for_second_file,
)
from artemis.parameters import ISPYB_PLAN_NAME, FullParameters
from artemis.zocalo_interaction import run_end, run_start, wait_for_result


class FGSCommunicator(CallbackBase):
    """Class for external communication (e.g. ispyb, zocalo...) during Artemis
    grid scan experiments.

    Listens to documents emitted by the RE and:
    - prepares nexus files
    - prepares ipsyb deposition
    - submits job to zocalo
    """

    def __init__(self, parameters: FullParameters):
        self.params = parameters
        self.descriptors: dict = {}
        ispyb_config = os.environ.get("ISPYB_CONFIG_PATH", "TEST_CONFIG")
        self.ispyb = (
            StoreInIspyb3D(ispyb_config, self.params)
            if self.params.grid_scan_params.is_3d_grid_scan
            else StoreInIspyb2D(ispyb_config, self.params)
        )
        self.processing_start_time = 0.0
        self.processing_time = 0.0
        self.nxs_writer_1 = NexusWriter(create_parameters_for_first_file(self.params))
        self.nxs_writer_2 = NexusWriter(create_parameters_for_second_file(self.params))
        self.results = None
        self.xray_centre_motor_position = None
        self.ispyb_ids: tuple = (None, None, None)
        self.datacollection_group_id = None

    def start(self, doc: dict):
        artemis.log.LOGGER.debug(f"\n\nReceived start document:\n\n {doc}\n")
        artemis.log.LOGGER.info("Creating Nexus files.")
        self.nxs_writer_1.create_nexus_file()
        self.nxs_writer_2.create_nexus_file()

    def descriptor(self, doc):
        self.descriptors[doc["uid"]] = doc

    def event(self, doc: dict):
        artemis.log.LOGGER.debug(f"\n\nReceived event document:\n{doc}\n")
        event_descriptor = self.descriptors[doc["descriptor"]]

        if event_descriptor.get("name") == ISPYB_PLAN_NAME:
            self.params.ispyb_params.undulator_gap = doc["data"]["fgs_undulator_gap"]
            self.params.ispyb_params.synchrotron_mode = doc["data"][
                "fgs_synchrotron_machine_status_synchrotron_mode"
            ]
            self.params.ispyb_params.slit_gap_size_x = doc["data"]["fgs_slit_gaps_xgap"]
            self.params.ispyb_params.slit_gap_size_y = doc["data"]["fgs_slit_gaps_ygap"]

            artemis.log.LOGGER.info("Creating ispyb entry.")
            self.ispyb_ids = self.ispyb.begin_deposition()
            datacollection_ids = self.ispyb_ids[0]
            self.datacollection_group_id = self.ispyb_ids[2]
            for id in datacollection_ids:
                run_start(id)

    def stop(self, doc: dict):
        artemis.log.LOGGER.debug(f"\n\nReceived stop document:\n\n {doc}\n")
        exit_status = doc.get("exit_status")

        artemis.log.LOGGER.debug("Updating Nexus file timestamps.")
        self.nxs_writer_1.update_nexus_file_timestamp()
        self.nxs_writer_2.update_nexus_file_timestamp()

        if self.ispyb_ids == (None, None, None):
            raise Exception("ispyb was not initialised at run start")
        self.ispyb.end_deposition(exit_status)
        datacollection_ids = self.ispyb_ids[0]
        for id in datacollection_ids:
            run_end(id)

    def wait_for_results(self):
        datacollection_group_id = self.ispyb_ids[2]
        self.results = wait_for_result(datacollection_group_id)
        self.processing_time = time.time() - self.processing_start_time
        self.xray_centre_motor_position = (
            self.params.grid_scan_params.grid_position_to_motor_position(self.results)
        )
        artemis.log.LOGGER.info(
            f"Results recieved from zocalo: {self.xray_centre_motor_position}"
        )
        artemis.log.LOGGER.info(f"Zocalo processing took {self.processing_time}s")
