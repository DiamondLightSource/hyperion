import time

import artemis.log
import artemis.zocalo_interaction
from artemis.nexus_writing.write_nexus import (
    NexusWriter,
    create_parameters_for_first_file,
    create_parameters_for_second_file,
)
from artemis.parameters import FullParameters


class FGSCommunicator:
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

    def cb(self, event_name, event_data):
        artemis.log.LOGGER.debug(
            f"FGSCommunicator.cb {self} recieved event '{event_name}' with document {event_data}"
        )
        artemis.log.LOGGER.debug(
            f"FGSCommunicator.cb processing event for run {event_data.get('run_start')} during run {self.active_uid}"
        )

        if event_name == "start":
            self.active_uid = event_data.get("uid")

            with NexusWriter(
                create_parameters_for_first_file(self.params)
            ), NexusWriter(create_parameters_for_second_file(self.params)):
                artemis.log.LOGGER.info(
                    f"Creating Nexus files for run {self.active_uid}"
                )

            artemis.log.LOGGER.info(f"Creating ispyb entry for run {self.active_uid}")
            # ispyb goes here

            artemis.log.LOGGER.info(f"Initialising Zocalo for run {self.active_uid}")
            # zocalo run_start goes here

        # if event_name == "event":
        # any live update stuff goes here

        if event_name == "stop":
            if event_data.get("run_start") != self.active_uid:
                raise Exception("Received document for a run which is not open")
            if event_data.get("exit_status") == "success":
                artemis.log.LOGGER.info(
                    f"Run {self.active_uid} successful, submitting data to zocalo"
                )
                # zocalo end_run goes here
                b4_processing = time.time()
                time.sleep(0.1)
                # self.results = waitforresults()
                self.processing_time = time.time() - b4_processing
                artemis.log.LOGGER.info(
                    f"Zocalo processing took {self.processing_time}s"
                )
