import json
from os.path import join

from artemis.devices.oav.oav_centring import OAVParameters


def test_oav_parameters_load_parameters_from_file(tmpdir):
    f_dict = {
        "exposure": 0.075,
        "acqPeriod": 0.05,
        "gain": 1.0,
        "minheight": 70,
        "oav": "OAV",
        "mxsc_input": "CAM",
        "min_callback_time": 0.080,
        "close_ksize": 11,
        "direction": 0,
        "loopCentring": {
            "zoom": 5.0,
            "preprocess": 8,
            "preProcessKSize": 21,
            "CannyEdgeUpperThreshold": 20.0,
            "CannyEdgeLowerThreshold": 5.0,
            "brightness": 20,
            "filename": "/dls_sw/prod/R3.14.12.7/support/adPython/2-1-11/adPythonApp/scripts/adPythonMxSampleDetect.py",
            "max_tip_distance": 300,
            "direction": 1,
        },
    }

    parameters = OAVParameters()
    with open(join(tmpdir, "OAVCentring.json"), "w") as write_file:
        json.dump(f_dict, write_file, indent=2)
    parameters.load_parameters_from_file(path=tmpdir)

    assert parameters.canny_edge_lower_threshold == 5.0
    assert parameters.close_ksize == 11
    assert parameters.direction == 1
