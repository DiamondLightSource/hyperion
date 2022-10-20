import time

from bluesky.callbacks import CallbackBase

import artemis.log
import artemis.zocalo_interaction
from artemis.nexus_writing.write_nexus import (
    NexusWriter,
    create_parameters_for_first_file,
    create_parameters_for_second_file,
)
from artemis.parameters import FullParameters

#
# class MyCallback(CallbackBase):
#     def start(self, doc):
#         print("I got a new 'start' Document")
#         # Do something
#     def descriptor(self, doc):
#         print("I got a new 'descriptor' Document")
#         # Do something
#     def event(self, doc):
#         print("I got a new 'event' Document")
#         # Do something
#     def stop(self, doc):
#         print("I got a new 'stop' Document")
#         # Do something


class FGSCommunicator(CallbackBase):
    """Class for external communication (e.g. ispyb, zocalo...) during Artemis
    grid scan experiments.

    Listens to events from the RE and submits:
    - nothing so far
    """

    def __init__(self):
        self.reset(FullParameters())

    def reset(self, parameters):
        self.active_uid = None
        self.params = parameters
        self.results = None
        self.processing_time = None
        self.nxs_writer_1 = NexusWriter(create_parameters_for_first_file(self.params))
        self.nxs_writer_2 = NexusWriter(create_parameters_for_second_file(self.params))

    #    def cb(self, event_name, doc):
    #        artemis.log.LOGGER.debug(
    #            f"FGSCommunicator.cb {self} recieved event '{event_name}' with document {doc}"
    #        )
    #        artemis.log.LOGGER.debug(
    #            f"FGSCommunicator.cb processing event for run {doc.get('run_start')} during run {self.active_uid}"
    #        )

    def start(self, doc):
        self.active_uid = doc.get("uid")

        artemis.log.LOGGER.info(f"Creating Nexus files for run {self.active_uid}")
        self.nxs_writer_1.create_nexus_file()
        self.nxs_writer_2.create_nexus_file()

        artemis.log.LOGGER.info(f"Creating ispyb entry for run {self.active_uid}")
        # ispyb goes here

        artemis.log.LOGGER.info(f"Initialising Zocalo for run {self.active_uid}")
        # zocalo run_start goes here

    # def event(self, doc):
    # any live update stuff goes here

    def stop(self, doc):
        if doc.get("run_start") != self.active_uid:
            raise Exception("Received document for a run which is not open")
        if doc.get("exit_status") == "success":
            artemis.log.LOGGER.debug("Updating Nexus file timestamps.")
            self.nxs_writer_1.update_nexus_file_timestamp()
            self.nxs_writer_2.update_nexus_file_timestamp()

            artemis.log.LOGGER.info(
                f"Run {self.active_uid} successful, submitting data to zocalo"
            )
            # zocalo end_run goes here

            b4_processing = time.time()
            time.sleep(0.1)
            # self.results = waitforresults()
            self.processing_time = time.time() - b4_processing
            artemis.log.LOGGER.info(f"Zocalo processing took {self.processing_time}s")
