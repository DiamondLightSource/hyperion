from __future__ import annotations

from bluesky.callbacks import CallbackBase

from hyperion.external_interaction.nexus.write_nexus import (
    CreateGoniometerProtocol,
    NexusWriter,
)
from hyperion.log import LOGGER
from hyperion.parameters.constants import ISPYB_HARDWARE_READ_PLAN
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)


class GridscanNexusFileCallback(CallbackBase):
    """Callback class to handle the creation of Nexus files based on experiment \
    parameters. Initialises on recieving a 'start' document for the \
    'run_gridscan_move_and_tidy' sub plan, which must also contain the run parameters, \
    as metadata under the 'hyperion_internal_parameters' key. Actually writes the \
    nexus files on updates the timestamps on recieving the 'ispyb_reading_hardware' event \
    document, and finalises the files on getting a 'stop' document for the whole run.

    To use, subscribe the Bluesky RunEngine to an instance of this class.
    E.g.:
        nexus_file_handler_callback = NexusFileCallback(parameters)
        RE.subscribe(nexus_file_handler_callback)
    Or decorate a plan using bluesky.preprocessors.subs_decorator.

    See: https://blueskyproject.io/bluesky/callbacks.html#ways-to-invoke-callbacks

    Usually used as part of an FGSCallbackCollection.
    """

    def __init__(self, create_goniometer_func: CreateGoniometerProtocol) -> None:
        self.parameters: GridscanInternalParameters | None = None
        self.run_start_uid: str | None = None
        self.nexus_writer_1: NexusWriter | None = None
        self.nexus_writer_2: NexusWriter | None = None
        self.create_goniometer_func = create_goniometer_func

    def start(self, doc: dict):
        if doc.get("subplan_name") == "run_gridscan_move_and_tidy":
            LOGGER.info(
                "Nexus writer recieved start document with experiment parameters."
            )
            json_params = doc.get("hyperion_internal_parameters")
            self.parameters = GridscanInternalParameters.from_json(json_params)
            self.run_start_uid = doc.get("uid")

    def descriptor(self, doc):
        if doc.get("name") == ISPYB_HARDWARE_READ_PLAN:
            assert (
                self.parameters is not None
            ), "Nexus callback did not receive parameters before being asked to write!"
            # TODO instead of ispyb wait for detector parameter reading in plan
            # https://github.com/DiamondLightSource/python-hyperion/issues/629
            # and update parameters before creating writers

            LOGGER.info("Initialising nexus writers")
            nexus_data_1 = self.parameters.get_nexus_info(1)
            LOGGER.info(f"Nexus data 1: {nexus_data_1}")
            nexus_data_2 = self.parameters.get_nexus_info(2)
            self.nexus_writer_1 = NexusWriter(
                self.parameters,
                create_goniometer_func=self.create_goniometer_func,
                **nexus_data_1,
            )
            self.nexus_writer_2 = NexusWriter(
                self.parameters,
                create_goniometer_func=self.create_goniometer_func,
                **nexus_data_2,
                vds_start_index=nexus_data_1["data_shape"][0],
            )
            self.nexus_writer_1.create_nexus_file()
            self.nexus_writer_2.create_nexus_file()


class Gridscan2DNexusFileCallback(CallbackBase):
    """Similar to above, but for a 2D gridscan"""

    def __init__(self, create_goniometer_func: CreateGoniometerProtocol) -> None:
        self.parameters: GridscanInternalParameters | None = None
        self.run_start_uid: str | None = None
        self.nexus_writer: NexusWriter | None = None
        self.create_goniometer_func = create_goniometer_func

    def start(self, doc: dict):
        if doc.get("subplan_name") == "run_gridscan_move_and_tidy":
            LOGGER.info(
                "Nexus writer recieved start document with experiment parameters."
            )
            json_params = doc.get("hyperion_internal_parameters")
            self.parameters = GridscanInternalParameters.from_json(json_params)
            self.run_start_uid = doc.get("uid")

    def descriptor(self, doc):
        if doc.get("name") == ISPYB_HARDWARE_READ_PLAN:
            assert (
                self.parameters is not None
            ), "Nexus callback did not receive parameters before being asked to write!"
            # TODO instead of ispyb wait for detector parameter reading in plan
            # https://github.com/DiamondLightSource/python-hyperion/issues/629
            # and update parameters before creating writers

            LOGGER.info("Initialising nexus writer")
            nexus_data = self.parameters.get_nexus_info(1)
            LOGGER.info(f"Nexus data: {nexus_data}")
            self.nexus_writer = NexusWriter(
                self.parameters,
                create_goniometer_func=self.create_goniometer_func,
                **nexus_data,
            )
            self.nexus_writer.create_nexus_file()
