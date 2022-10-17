import artemis.log
import artemis.zocalo_interaction


class FGSRecommender:
    """Listens to events from the RE and submits:
    - nothing so far
    """

    def __init__(self):
        self.active_uid = None

    def cb(self, event_name, event_data):
        artemis.log.LOGGER.info(
            f"FGSRecommender.cb {self} recieved event '{event_name}' with document {event_data}"
        )
        artemis.log.LOGGER.info(
            f"FGSRecommender.cb processing event for run {event_data.get('run_start')} during run {self.active_uid}"
        )

        if event_name == "start":
            self.active_uid = event_data.get("uid")

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

            self.active_uid = None
