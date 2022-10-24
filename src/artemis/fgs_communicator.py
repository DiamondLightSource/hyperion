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
from artemis.parameters import FullParameters
from artemis.zocalo_interaction import run_end, run_start, wait_for_result


class FGSCommunicator(CallbackBase):
    """Class for external communication (e.g. ispyb, zocalo...) during Artemis
    grid scan experiments.

    Listens to documents emitted by the RE and:
    - prepares nexus files
    - prepares ipsyb deposition
    - submits job to zocalo
    """

    def __init__(self):
        self.reset(FullParameters())

    def reset(self, parameters: FullParameters):
        self.active_uid = None
        self.gridscan_uid = None
        self.params = parameters
        self.params.detector_params.prefix += str(time.time())
        self.results = None
        self.processing_time = None
        self.nxs_writer_1 = NexusWriter(create_parameters_for_first_file(self.params))
        self.nxs_writer_2 = NexusWriter(create_parameters_for_second_file(self.params))
        self.datacollection_group_id = None
        self.xray_centre_motor_position = None
        self.ispyb_ids = None
        self.descriptors: dict = {}

    def start(self, doc: dict):
        artemis.log.LOGGER.debug(f"\n\nReceived start document:\n\n {doc}\n")
        self.active_uid = doc.get("uid")
        # exceptionally, do write nexus files for fake scan
        #    if self.params.scan_type == "fake_scan":
        #    return
        if doc.get("plan_name") not in ["run_gridscan", "fake_scan"]:
            return
        self.gridscan_uid = doc.get("uid")

        artemis.log.LOGGER.info(f"Creating Nexus files for run {self.active_uid}")
        self.nxs_writer_1.create_nexus_file()
        self.nxs_writer_2.create_nexus_file()

        artemis.log.LOGGER.info(f"Initialising Zocalo for run {self.active_uid}")
        # zocalo run_start goes here

    def get_descriptor_doc(self, key) -> dict:
        associated_descriptor_doc = self.descriptors.get(key)
        if type(associated_descriptor_doc) is not dict:
            raise ValueError(
                "Non-dict object stored in descriptor list, or key not valid."
            )
        return associated_descriptor_doc

    # TODO is this going to eat too much memory if there are a lot of these with a lot of data?
    def descriptor(self, doc: dict):
        artemis.log.LOGGER.debug(f"\n\nReceived descriptor document:\n\n {doc}\n")
        self.descriptors[doc.get("uid")] = doc

    def event(self, doc: dict):
        run_start_uid = self.get_descriptor_doc(doc.get("descriptor")).get("run_start")
        artemis.log.LOGGER.debug(f"\n\nReceived event document:\n\n {doc}\n")
        if self.params.scan_type == "fake_scan":
            return
        # Don't do processing for move_xyz
        if run_start_uid != self.gridscan_uid:
            return
        if doc.get("name") == "ispyb_motor_positions":
            self.params.ispyb_params.undulator_gap = doc["data"]["undulator_gap"]
            self.params.ispyb_params.synchrotron_mode = doc["data"][
                "synchrotron_machine_status_synchrotron_mode"
            ]
            self.params.ispyb_params.slit_gap_size_x = doc["data"]["slit_gaps_xgap"]
            self.params.ispyb_params.slit_gap_size_y = doc["data"]["slit_gaps_ygap"]

            artemis.log.LOGGER.info(f"Creating ispyb entry for run {self.active_uid}")
            ispyb_config = os.environ.get("ISPYB_CONFIG_PATH", "TEST_CONFIG")

            ispyb = (
                StoreInIspyb3D(ispyb_config, self.params)
                if self.params.grid_scan_params.is_3d_grid_scan
                else StoreInIspyb2D(ispyb_config, self.params)
            )

            with ispyb as ispyb_ids:
                self.ispyb_ids = ispyb_ids
                datacollection_ids = ispyb_ids[0]
                self.datacollection_group_id = ispyb_ids[2]
                for id in datacollection_ids:
                    run_start(id)

        # any live update stuff goes here

    def stop(self, doc: dict):
        artemis.log.LOGGER.debug(f"\n\nReceived stop document:\n\n {doc}\n")
        if self.params.scan_type == "fake_scan":
            return
        # Don't do processing for move_xyz
        if doc.get("run_start") != self.gridscan_uid:
            return
        if doc.get("exit_status") == "success":
            artemis.log.LOGGER.debug("Updating Nexus file timestamps.")
            self.nxs_writer_1.update_nexus_file_timestamp()
            self.nxs_writer_2.update_nexus_file_timestamp()

            if self.ispyb_ids is None:
                raise Exception("ispyb was not initialised at run start")
            datacollection_ids = self.ispyb_ids[0]
            for id in datacollection_ids:
                run_end(id)

            artemis.log.LOGGER.info(
                f"Run {self.active_uid} successful, submitting data to zocalo"
            )
            self.results = wait_for_result(self.datacollection_group_id)
            self.xray_centre_motor_position = (
                self.params.grid_scan_params.grid_position_to_motor_position(
                    self.results
                )
            )

            b4_processing = time.time()
            time.sleep(0.1)  # TODO remove once actual mock processing exists
            # self.results = waitforresults()
            self.processing_time = time.time() - b4_processing
            artemis.log.LOGGER.info(f"Zocalo processing took {self.processing_time}s")
