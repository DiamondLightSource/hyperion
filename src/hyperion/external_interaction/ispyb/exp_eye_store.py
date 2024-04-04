import configparser
from typing import Dict, Tuple

from requests import patch, post
from requests.auth import AuthBase

from hyperion.external_interaction.exceptions import ISPyBDepositionNotMade
from hyperion.external_interaction.ispyb.ispyb_utils import (
    get_current_time_string,
    get_ispyb_config,
)

RobotActionID = int


class BearerAuth(AuthBase):
    def __init__(self, token):
        self.token = token

    def __call__(self, r):
        r.headers["authorization"] = "Bearer " + self.token
        return r


def _get_base_url_and_token() -> Tuple[str, str]:
    config = configparser.ConfigParser()
    conf = get_ispyb_config()
    config.read(conf)
    expeye_config = config["expeye"]
    return expeye_config["url"], expeye_config["token"]


class ExpeyeInteraction:
    CREATE_ROBOT_ACTION = "/proposals/{proposal}/sessions/{visit_number}/robot-actions"
    UPDATE_ROBOT_ACTION = "/robot-actions/{action_id}"

    def __init__(self) -> None:
        url, token = _get_base_url_and_token()
        self.base_url = url + "/core"
        self.auth = BearerAuth(token)

    def _send_and_get_response(self, url, data, send_func) -> Dict:
        response = send_func(url, auth=self.auth, json=data)
        if not response.ok:
            raise ISPyBDepositionNotMade(f"Could not write {data} to {url}: {response}")
        return response.json()

    def start_load(
        self,
        proposal_reference: str,
        visit_number: int,
        sample_id: int,
        dewar_location: int,
        container_location: int,
    ) -> RobotActionID:
        url = self.base_url + self.CREATE_ROBOT_ACTION.format(
            proposal=proposal_reference, visit_number=visit_number
        )

        data = {
            "startTimestamp": get_current_time_string(),
            "sampleId": sample_id,
            "actionType": "LOAD",
            "containerLocation": container_location,
            "dewarLocation": dewar_location,
        }
        response = self._send_and_get_response(url, data, post)
        return response["robotActionId"]

    def end_load(self, action_id: RobotActionID, status: str, reason: str):
        url = self.base_url + self.UPDATE_ROBOT_ACTION.format(action_id=action_id)

        run_status = "SUCCESS" if status == "success" else "ERROR"

        data = {
            "endTimestamp": get_current_time_string(),
            "status": run_status,
            "message": reason,
        }
        self._send_and_get_response(url, data, patch)
