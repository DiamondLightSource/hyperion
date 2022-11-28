import os
import time
from typing import Dict, NamedTuple

from bluesky.callbacks import CallbackBase

from artemis.external_interaction.ispyb.store_in_ispyb import (
    StoreInIspyb2D,
    StoreInIspyb3D,
)
from artemis.external_interaction.nexus_writing.write_nexus import (
    NexusWriter,
    create_parameters_for_first_file,
    create_parameters_for_second_file,
)
from artemis.external_interaction.zocalo_interaction import (
    run_end,
    run_start,
    wait_for_result,
)
from artemis.log import LOGGER
from artemis.parameters import SIM_ISPYB_CONFIG, ISPYB_PLAN_NAME, FullParameters
from artemis.utils import Point3D


class ISPyBDepositionNotMade(Exception):
    """Raised when the ISPyB or Zocalo callbacks can't access ISPyB deposition numbers."""

    pass


class NexusFileHandlerCallback(CallbackBase):
    """Callback class to handle the creation of Nexus files based on experiment
    parameters. Creates the Nexus files on recieving a 'start' document, and updates the
    timestamps on recieving a 'stop' document.

    To use, subscribe the Bluesky RunEngine to an instance of this class.
    E.g.:
        nexus_file_handler_callback = NexusFileHandlerCallback(parameters)
        RE.subscribe(nexus_file_handler_callback)

    Or decorate a plan using bluesky.preprocessors.subs_decorator.
    See: https://blueskyproject.io/bluesky/callbacks.html#ways-to-invoke-callbacks
    """

    def __init__(self, parameters: FullParameters):
        self.nxs_writer_1 = NexusWriter(create_parameters_for_first_file(parameters))
        self.nxs_writer_2 = NexusWriter(create_parameters_for_second_file(parameters))

    def start(self, doc: dict):
        LOGGER.debug(f"\n\nReceived start document:\n\n {doc}\n")
        LOGGER.info("Creating Nexus files.")
        self.nxs_writer_1.create_nexus_file()
        self.nxs_writer_2.create_nexus_file()

    def stop(self, doc: dict):
        LOGGER.debug("Updating Nexus file timestamps.")
        self.nxs_writer_1.update_nexus_file_timestamp()
        self.nxs_writer_2.update_nexus_file_timestamp()


class ISPyBHandlerCallback(CallbackBase):
    """Callback class to handle the deposition of experiment parameters into the ISPyB
    database. Listens for 'event' and 'descriptor' documents.

    To use, subscribe the Bluesky RunEngine to an instance of this class.
    E.g.:
        nexus_file_handler_callback = NexusFileHandlerCallback(parameters)
        RE.subscribe(nexus_file_handler_callback)

    Or decorate a plan using bluesky.preprocessors.subs_decorator.
    See: https://blueskyproject.io/bluesky/callbacks.html#ways-to-invoke-callbacks
    """

    def __init__(self, parameters: FullParameters):
        self.params = parameters
        self.descriptors: Dict[str, dict] = {}
        ispyb_config = os.environ.get("ISPYB_CONFIG_PATH", SIM_ISPYB_CONFIG)
        self.ispyb = (
            StoreInIspyb3D(ispyb_config, self.params)
            if self.params.grid_scan_params.is_3d_grid_scan
            else StoreInIspyb2D(ispyb_config, self.params)
        )
        self.ispyb_ids: tuple = (None, None, None)

    def descriptor(self, doc):
        self.descriptors[doc["uid"]] = doc

    def event(self, doc: dict):
        LOGGER.debug(f"\n\nISPyB handler received event document:\n{doc}\n")
        event_descriptor = self.descriptors[doc["descriptor"]]

        if event_descriptor.get("name") == ISPYB_PLAN_NAME:
            self.params.ispyb_params.undulator_gap = doc["data"]["fgs_undulator_gap"]
            self.params.ispyb_params.synchrotron_mode = doc["data"][
                "fgs_synchrotron_machine_status_synchrotron_mode"
            ]
            self.params.ispyb_params.slit_gap_size_x = doc["data"]["fgs_slit_gaps_xgap"]
            self.params.ispyb_params.slit_gap_size_y = doc["data"]["fgs_slit_gaps_ygap"]

            LOGGER.info("Creating ispyb entry.")
            self.ispyb_ids = self.ispyb.begin_deposition()

    def stop(self, doc: dict):
        LOGGER.debug(f"\n\nISPyB handler received stop document:\n\n {doc}\n")
        exit_status = doc.get("exit_status")
        reason = doc.get("reason")
        if self.ispyb_ids == (None, None, None):
            raise ISPyBDepositionNotMade("ispyb was not initialised at run start")
        self.ispyb.end_deposition(exit_status, reason)


class ZocaloHandlerCallback(CallbackBase):
    """Callback class to handle the triggering of Zocalo processing.
    Listens for 'event' and 'stop' documents.

    Needs to be connected to an ISPyBHandlerCallback subscribed to the same run in order
    to have access to the deposition numbers to pass on to Zocalo.

    To use, subscribe the Bluesky RunEngine to an instance of this class.
    E.g.:
        nexus_file_handler_callback = NexusFileHandlerCallback(parameters)
        RE.subscribe(nexus_file_handler_callback)

    Or decorate a plan using bluesky.preprocessors.subs_decorator.
    See: https://blueskyproject.io/bluesky/callbacks.html#ways-to-invoke-callbacks
    """

    def __init__(self, parameters: FullParameters, ispyb_handler: ISPyBHandlerCallback):
        self.grid_position_to_motor_position = (
            parameters.grid_scan_params.grid_position_to_motor_position
        )
        self.processing_start_time = 0.0
        self.processing_time = 0.0
        self.results = None
        self.xray_centre_motor_position = None
        self.ispyb = ispyb_handler

    def event(self, doc: dict):
        LOGGER.debug(f"\n\nZocalo handler received event document:\n\n {doc}\n")
        descriptor = self.ispyb.descriptors.get(doc["descriptor"])
        assert descriptor is not None
        event_name = descriptor.get("name")
        if event_name == ISPYB_PLAN_NAME:
            if self.ispyb.ispyb_ids[0] is not None:
                datacollection_ids = self.ispyb.ispyb_ids[0]
                for id in datacollection_ids:
                    run_start(id)
            else:
                raise ISPyBDepositionNotMade("ISPyB deposition was not initialised!")

    def stop(self, doc: dict):
        LOGGER.debug(f"\n\nZocalo handler received stop document:\n\n {doc}\n")
        if self.ispyb.ispyb_ids == (None, None, None):
            raise ISPyBDepositionNotMade("ISPyB deposition was not initialised!")
        datacollection_ids = self.ispyb.ispyb_ids[0]
        for id in datacollection_ids:
            run_end(id)
        self.processing_start_time = time.time()

    def wait_for_results(self):
        datacollection_group_id = self.ispyb.ispyb_ids[2]
        raw_results = wait_for_result(datacollection_group_id)
        self.processing_time = time.time() - self.processing_start_time
        # wait_for_result returns the centre of the grid box, but we want the corner
        self.results = Point3D(
            raw_results.x - 0.5, raw_results.y - 0.5, raw_results.z - 0.5
        )
        self.xray_centre_motor_position = self.grid_position_to_motor_position(
            self.results
        )

        LOGGER.info(f"Results recieved from zocalo: {self.xray_centre_motor_position}")
        LOGGER.info(f"Zocalo processing took {self.processing_time}s")


class FGSCallbackCollection(NamedTuple):
    """Groups the callbacks for external interactions in the fast grid scan, and
    connects the Zocalo and ISPyB handlers. Cast to a list to pass it to
    Bluesky.preprocessors.subs_decorator()."""

    # Callbacks are triggered in this order, which is important: ISPyB deposition must
    # be initialised before the Zocalo handler can do its thing.
    nexus_handler: NexusFileHandlerCallback
    ispyb_handler: ISPyBHandlerCallback
    zocalo_handler: ZocaloHandlerCallback

    @classmethod
    def from_params(cls, parameters: FullParameters):
        nexus_handler = NexusFileHandlerCallback(parameters)
        ispyb_handler = ISPyBHandlerCallback(parameters)
        zocalo_handler = ZocaloHandlerCallback(parameters, ispyb_handler)
        callback_collection = cls(
            nexus_handler=nexus_handler,
            ispyb_handler=ispyb_handler,
            zocalo_handler=zocalo_handler,
        )
        return callback_collection
