from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from hyperion.external_interaction.callbacks.ispyb_callback_base import (
    BaseISPyBCallback,
)
from hyperion.external_interaction.ispyb.ispyb_store import (
    IspybIds,
)
from hyperion.external_interaction.ispyb.rotation_ispyb_store import (
    StoreRotationInIspyb,
)
from hyperion.log import ISPYB_LOGGER, set_dcgid_tag
from hyperion.parameters.constants import CONST
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)

if TYPE_CHECKING:
    from event_model.documents import Event, RunStart, RunStop


class RotationISPyBCallback(BaseISPyBCallback):
    """Callback class to handle the deposition of experiment parameters into the ISPyB
    database. Listens for 'event' and 'descriptor' documents. Creates the ISpyB entry on
    recieving an 'event' document for the 'ispyb_reading_hardware' event, and updates the
    deposition on recieving its final 'stop' document.

    To use, subscribe the Bluesky RunEngine to an instance of this class.
    E.g.:
        ispyb_handler_callback = RotationISPyBCallback(parameters)
        RE.subscribe(ispyb_handler_callback)
    Or decorate a plan using bluesky.preprocessors.subs_decorator.

    See: https://blueskyproject.io/bluesky/callbacks.html#ways-to-invoke-callbacks

    Usually used as part of a RotationCallbackCollection.
    """

    def __init__(
        self,
        *,
        emit: Callable[..., Any] | None = None,
    ) -> None:
        super().__init__(emit=emit)
        self.last_sample_id: str | None = None
        self.ispyb_ids: IspybIds = IspybIds()

    def activity_gated_start(self, doc: RunStart):
        if doc.get("subplan_name") == CONST.PLAN.ROTATION_OUTER:
            ISPYB_LOGGER.info(
                "ISPyB callback recieved start document with experiment parameters."
            )
            json_params = doc.get("hyperion_internal_parameters")
            self.params = RotationInternalParameters.from_json(json_params)
            dcgid = (
                self.ispyb_ids.data_collection_group_id
                if (
                    self.params.hyperion_params.ispyb_params.sample_id
                    == self.last_sample_id
                )
                else None
            )
            n_images = self.params.experiment_params.get_num_images()
            if n_images < 200:
                ISPYB_LOGGER.info(
                    f"Collection has {n_images} images - treating as a screening collection - new DCG"
                )
                dcgid = None
                self.last_sample_id = None
            else:
                ISPYB_LOGGER.info(
                    f"Collection has {n_images} images - treating as a genuine dataset - storing sampleID to bundle images"
                )
                self.last_sample_id = self.params.hyperion_params.ispyb_params.sample_id
            experiment_type = (
                self.params.hyperion_params.ispyb_params.ispyb_experiment_type
            )
            if experiment_type:
                self.ispyb = StoreRotationInIspyb(
                    self.ispyb_config,
                    self.params,
                    dcgid,
                    experiment_type,
                )
            else:
                self.ispyb = StoreRotationInIspyb(self.ispyb_config, self.params, dcgid)
            ISPYB_LOGGER.info("Beginning ispyb deposition")
            self.ispyb_ids = self.ispyb.begin_deposition()
        ISPYB_LOGGER.info("ISPYB handler received start document.")
        if doc.get("subplan_name") == CONST.PLAN.ROTATION_MAIN:
            self.uid_to_finalize_on = doc.get("uid")
        return super().activity_gated_start(doc)

    def activity_gated_event(self, doc: Event):
        doc = super().activity_gated_event(doc)
        set_dcgid_tag(self.ispyb_ids.data_collection_group_id)
        return doc

    def activity_gated_stop(self, doc: RunStop) -> None:
        if doc.get("run_start") == self.uid_to_finalize_on:
            self.uid_to_finalize_on = None
            return super().activity_gated_stop(doc)
        return self._tag_doc(doc)
