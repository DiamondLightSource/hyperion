from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, TypeVar

from hyperion.external_interaction.callbacks.plan_reactive_callback import (
    PlanReactiveCallback,
)
from hyperion.external_interaction.ispyb.ispyb_store import (
    IspybIds,
    StoreInIspyb,
)
from hyperion.external_interaction.ispyb.ispyb_utils import get_ispyb_config
from hyperion.log import ISPYB_LOGGER, set_dcgid_tag
from hyperion.parameters.constants import CONST
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)

D = TypeVar("D")
if TYPE_CHECKING:
    from event_model.documents import Event, EventDescriptor, RunStart, RunStop


class BaseISPyBCallback(PlanReactiveCallback):
    def __init__(
        self,
        *,
        emit: Callable[..., Any] | None = None,
    ) -> None:
        """Subclasses should run super().__init__() with parameters, then set
        self.ispyb to the type of ispyb relevant to the experiment and define the type
        for self.ispyb_ids."""
        ISPYB_LOGGER.debug("Initialising ISPyB callback")
        super().__init__(log=ISPYB_LOGGER, emit=emit)
        self.params: GridscanInternalParameters | RotationInternalParameters | None = (
            None
        )
        self.ispyb: StoreInIspyb
        self.descriptors: Dict[str, EventDescriptor] = {}
        self.ispyb_config = get_ispyb_config()
        if (
            self.ispyb_config == CONST.SIM.ISPYB_CONFIG
            or self.ispyb_config == CONST.SIM.DEV_ISPYB_DATABASE_CFG
        ):
            ISPYB_LOGGER.warning(
                f"{self.__class__} using dev ISPyB config: {self.ispyb_config}. If you"
                "want to use the real database, please set the ISPYB_CONFIG_PATH "
                "environment variable."
            )
        self.uid_to_finalize_on: Optional[str] = None
        self.ispyb_ids: IspybIds = IspybIds()
        self.log = ISPYB_LOGGER

    def activity_gated_start(self, doc: RunStart):
        return self._tag_doc(doc)

    def activity_gated_descriptor(self, doc: EventDescriptor):
        self.descriptors[doc["uid"]] = doc
        return self._tag_doc(doc)

    def activity_gated_event(self, doc: Event) -> Event:
        """Subclasses should extend this to add a call to set_dcig_tag from
        hyperion.log"""
        ISPYB_LOGGER.debug("ISPyB handler received event document.")
        assert self.ispyb is not None, "ISPyB deposition wasn't initialised!"
        assert self.params is not None, "ISPyB handler didn't recieve parameters!"

        event_descriptor = self.descriptors.get(doc["descriptor"])
        if event_descriptor is None:
            ISPYB_LOGGER.warning(
                f"Ispyb handler {self} recieved event doc {doc} and "
                "has no corresponding descriptor record"
            )
            return doc
        if event_descriptor.get("name") == CONST.PLAN.ISPYB_HARDWARE_READ:
            ISPYB_LOGGER.info("ISPyB handler received event from read hardware")
            self.params.hyperion_params.ispyb_params.undulator_gap = doc["data"][
                "undulator_current_gap"
            ]
            self.params.hyperion_params.ispyb_params.synchrotron_mode = doc["data"][
                "synchrotron-synchrotron_mode"
            ]
            self.params.hyperion_params.ispyb_params.slit_gap_size_x = doc["data"][
                "s4_slit_gaps_xgap"
            ]
            self.params.hyperion_params.ispyb_params.slit_gap_size_y = doc["data"][
                "s4_slit_gaps_ygap"
            ]
            self.params.hyperion_params.ispyb_params.sample_barcode = doc["data"][
                "robot-barcode"
            ]

        if event_descriptor.get("name") == CONST.PLAN.ISPYB_TRANSMISSION_FLUX_READ:
            self.params.hyperion_params.ispyb_params.transmission_fraction = doc[
                "data"
            ]["attenuator_actual_transmission"]
            self.params.hyperion_params.ispyb_params.flux = doc["data"][
                "flux_flux_reading"
            ]
            self.params.hyperion_params.ispyb_params.current_energy_ev = (
                doc["data"]["dcm_energy_in_kev"] * 1000
            )

            ISPYB_LOGGER.info("Updating ispyb entry.")
            self.ispyb_ids = self.update_deposition(self.params)
            ISPYB_LOGGER.info(f"Recieved ISPYB IDs: {self.ispyb_ids}")
        return self._tag_doc(doc)

    @abstractmethod
    def update_deposition(self, params) -> IspybIds:
        pass

    def activity_gated_stop(self, doc: RunStop) -> RunStop:
        """Subclasses must check that they are recieving a stop document for the correct
        uid to use this method!"""
        assert isinstance(
            self.ispyb, StoreInIspyb
        ), "ISPyB handler recieved stop document, but deposition object doesn't exist!"
        ISPYB_LOGGER.debug("ISPyB handler received stop document.")
        exit_status = (
            doc.get("exit_status") or "Exit status not available in stop document!"
        )
        reason = doc.get("reason") or ""
        set_dcgid_tag(None)
        try:
            self.ispyb.end_deposition(self.ispyb_ids, exit_status, reason)
        except Exception as e:
            ISPYB_LOGGER.warning(
                f"Failed to finalise ISPyB deposition on stop document: {doc} with exception: {e}"
            )
        return self._tag_doc(doc)

    def _append_to_comment(self, id: int, comment: str) -> None:
        assert isinstance(self.ispyb, StoreInIspyb)
        try:
            self.ispyb.append_to_comment(id, comment)
        except TypeError:
            ISPYB_LOGGER.warning(
                "ISPyB deposition not initialised, can't update comment."
            )

    def append_to_comment(self, comment: str):
        for id in self.ispyb_ids.data_collection_ids:
            self._append_to_comment(id, comment)

    def _tag_doc(self, doc: D) -> D:
        assert isinstance(doc, dict)
        if self.ispyb_ids:
            doc["ispyb_dcids"] = self.ispyb_ids.data_collection_ids
        return doc
