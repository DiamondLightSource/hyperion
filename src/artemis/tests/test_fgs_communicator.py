import pytest

from artemis import fgs_communicator
from artemis.parameters import FullParameters


def test_fgs_communicator_reset():
    communicator = fgs_communicator.FGSCommunicator()
    assert communicator.processing_time is None
    assert communicator.active_uid is None
    communicator.params.detector_params.prefix = "file_name"
    assert communicator.params == FullParameters()

    communicator.results = "some position to move to"
    communicator.reset(FullParameters())
    assert communicator.results is None


def test_start_sets_uid():
    communicator = fgs_communicator.FGSCommunicator()
    communicator.start({"uid": "some uid"})
    assert communicator.active_uid == "some uid"


def test_stop_excepts_on_wrong_uid():
    communicator = fgs_communicator.FGSCommunicator()
    communicator.active_uid = "some uid"
    with pytest.raises(Exception):
        communicator.stop({"run_start": "some other uid"})


def test_stop_doesnt_except_on_correct_uid():
    communicator = fgs_communicator.FGSCommunicator()
    communicator.active_uid = "some uid"
    communicator.stop({"run_start": "some uid"})
