import os
from time import sleep

import pytest

from hyperion.external_interaction.ispyb.exp_eye_store import ExpeyeInteraction
from hyperion.parameters.constants import CONST


@pytest.mark.s03
def test_start_and_end_robot_load():
    os.environ["ISPYB_CONFIG_PATH"] = CONST.SIM.DEV_ISPYB_DATABASE_CFG

    expeye = ExpeyeInteraction()

    robot_action_id = expeye.start_load("cm37235", 2, 5289780, 40, 3)

    sleep(0.5)

    expeye.update_barcode(robot_action_id, "test_barcode")

    sleep(0.5)

    expeye.end_load(robot_action_id, "fail", "Oh no!")

    # There is currently no way to get robot load info using expeye so to confirm for
    # now manually check https://ispyb-test.diamond.ac.uk/dc/visit/cm37235-2
