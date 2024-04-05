import os
from time import sleep

import pytest
from requests import get

from hyperion.external_interaction.ispyb.exp_eye_store import ExpeyeInteraction
from hyperion.parameters.constants import CONST


@pytest.mark.s03
def test_start_and_end_robot_load():
    os.environ["ISPYB_CONFIG_PATH"] = CONST.SIM.DEV_ISPYB_DATABASE_CFG

    SAMPLE_ID = 5289780
    BARCODE = "test_barcode"

    expeye = ExpeyeInteraction()

    robot_action_id = expeye.start_load("cm37235", 2, SAMPLE_ID, 40, 3)

    sleep(0.5)

    print(f"Created {robot_action_id}")

    expeye.update_barcode(robot_action_id, BARCODE)

    sleep(0.5)

    expeye.end_load(robot_action_id, "fail", "Oh no!")

    get_robot_data_url = f"{expeye.base_url}/robot-actions/{robot_action_id}"
    response = get(get_robot_data_url, auth=expeye.auth)

    assert response.ok

    response = response.json()
    assert response["robotActionId"] == robot_action_id
    assert response["status"] == "ERROR"
    assert response["sampleId"] == SAMPLE_ID
    assert response["sampleBarcode"] == BARCODE
