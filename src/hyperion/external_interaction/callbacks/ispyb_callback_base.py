from __future__ import annotations

from abc import abstractmethod
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, TypeVar

from hyperion.external_interaction.callbacks.common.ispyb_mapping import (
    populate_data_collection_group,
)
from hyperion.external_interaction.callbacks.plan_reactive_callback import (
    PlanReactiveCallback,
)
from hyperion.external_interaction.ispyb.data_model import (
    DataCollectionInfo,
    ScanDataInfo,
)
from hyperion.external_interaction.ispyb.ispyb_store import (
    IspybIds,
    StoreInIspyb,
)
from hyperion.external_interaction.ispyb.ispyb_utils import get_ispyb_config
from hyperion.log import ISPYB_LOGGER, set_dcgid_tag
from hyperion.parameters.constants import CONST
from hyperion.parameters.internal_parameters import InternalParameters
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)
from hyperion.utils.utils import convert_eV_to_angstrom

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
        self._event_driven_data_collection_info: Optional[DataCollectionInfo] = None
        self._sample_barcode: Optional[str] = None
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
        self._event_driven_data_collection_info = DataCollectionInfo()
        self._sample_barcode = None
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
            assert self._event_driven_data_collection_info
            ISPYB_LOGGER.info("ISPyB handler received event from read hardware")
            self._event_driven_data_collection_info.undulator_gap1 = doc["data"][
                "undulator_current_gap"
            ]
            self._event_driven_data_collection_info.synchrotron_mode = doc["data"][
                "synchrotron-synchrotron_mode"
            ]
            self._event_driven_data_collection_info.slitgap_horizontal = doc["data"][
                "s4_slit_gaps_xgap"
            ]
            self._event_driven_data_collection_info.slitgap_vertical = doc["data"][
                "s4_slit_gaps_ygap"
            ]
            self._sample_barcode = doc["data"]["robot-barcode"]

        if event_descriptor.get("name") == CONST.PLAN.ISPYB_TRANSMISSION_FLUX_READ:
            assert self._event_driven_data_collection_info
            if doc["data"]["attenuator_actual_transmission"]:
                # Ispyb wants the transmission in a percentage, we use fractions
                self._event_driven_data_collection_info.transmission = (
                    doc["data"]["attenuator_actual_transmission"] * 100
                )
                # TODO 1173 Remove this once nexus_utils no longer needs it
                self.params.hyperion_params.ispyb_params.transmission_fraction = doc[
                    "data"
                ]["attenuator_actual_transmission"]
            self._event_driven_data_collection_info.flux = doc["data"][
                "flux_flux_reading"
            ]
            # TODO 1173 Remove this once nexus_utils no longer needs it
            self.params.hyperion_params.ispyb_params.flux = (
                self._event_driven_data_collection_info.flux
            )
            if doc["data"]["dcm_energy_in_kev"]:
                energy_ev = doc["data"]["dcm_energy_in_kev"] * 1000
                self._event_driven_data_collection_info.wavelength = (
                    convert_eV_to_angstrom(energy_ev)
                )

            scan_data_infos = self.populate_info_for_update(
                self._event_driven_data_collection_info, self.params
            )
            ISPYB_LOGGER.info("Updating ispyb entry.")
            self.ispyb_ids = self.update_deposition(
                self.params,
                scan_data_infos,
                self._sample_barcode,
            )
            ISPYB_LOGGER.info(f"Recieved ISPYB IDs: {self.ispyb_ids}")
        return self._tag_doc(doc)

    def update_deposition(
        self,
        params,
        scan_data_infos: Sequence[ScanDataInfo],
        sample_barcode: Optional[str],
    ) -> IspybIds:
        data_collection_group_info = populate_data_collection_group(
            self.ispyb.experiment_type,
            params.hyperion_params.detector_params,
            params.hyperion_params.ispyb_params,
            sample_barcode,
        )

        return self.ispyb.update_deposition(
            self.ispyb_ids, data_collection_group_info, scan_data_infos
        )

    @abstractmethod
    def populate_info_for_update(
        self,
        event_sourced_data_collection_info: DataCollectionInfo,
        params: InternalParameters,
    ) -> Sequence[ScanDataInfo]:
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
