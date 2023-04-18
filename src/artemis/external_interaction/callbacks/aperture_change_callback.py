from bluesky.callbacks import CallbackBase

from artemis.log import LOGGER


class ApertureChangeCallback(CallbackBase):
    last_selected_aperture: str = "NONE"

    def start(self, doc: dict):
        if doc.get("subplan_name") == "change_aperture":
            LOGGER.info(f"START: {doc}")
            ap_size = doc.get("aperture_size")
            assert isinstance(ap_size, str)
            LOGGER.info(f"Updating most recent in-plan aperture change to {ap_size}.")
            self.last_selected_aperture = ap_size
