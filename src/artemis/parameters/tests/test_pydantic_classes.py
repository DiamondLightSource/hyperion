from pydantic import BaseModel

from artemis.external_interaction.ispyb.ispyb_dataclass import (
    GRIDSCAN_ISPYB_PARAM_DEFAULTS,
    GridscanIspybParams,
    IspybParams,
)


class FirstModel(BaseModel):
    x: int


class SecondModel(FirstModel):
    y: int


data = {"x": 3, "y": 4}


def test_first_model():
    first = FirstModel(**data)


def test_second_model():
    second = SecondModel(**data)


def test_first_isp_model():
    first = IspybParams(**GRIDSCAN_ISPYB_PARAM_DEFAULTS)


def test_second_isp_model():
    second = GridscanIspybParams(**GRIDSCAN_ISPYB_PARAM_DEFAULTS)
    assert second.visit_path == ""
