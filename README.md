# python-artemis

Repository for the Artemis project to implement "3D grid scans" using the BlueSky / Ophyd framework from BNL. 

https://nsls-ii.github.io/bluesky/


Development Installation
=================

1. Clone this project 
1. If on a DLS machine avoid the controls pypi server and get Python 3.7 by running:
    ```
    module unload controls_dev
    module load python/3.7
    ```
    If not at DLS, use your local version of Python 3.7
1. Gather the dependencies by running the following
    ```
    pipenv install --dev
    ```
1. Install the pre-commit hooks, as specified [here](https://pre-commit.com/#3-install-the-git-hook-scripts).


Controlling the Gridscan Externally (e.g. from GDA)
=====================

Starting the bluesky runner
-------------------------
You can start the bluesky runner by doing the following:
```
pipenv run python src/artemis/main.py
```

Starting a scan
--------------

To start a scan you can do the following:
```
curl -X PUT http://127.0.0.1:5000/fast_grid_scan/start -d 'PARAMS' -H "Content-Type: application/json"
```

where `PARAMS` is some JSON of the following form:
```
{'beamline': 'BL03S',
 'detector': 'EIGER2_X_16M',
 'detector_params': {'acquisition_id': 'test',
                     'current_energy': 100,
                     'detector_distance': 100.0,
                     'directory': '/tmp',
                     'exposure_time': 0.1,
                     'num_images': 10,
                     'omega_increment': 0.1,
                     'omega_start': 0.0,
                     'prefix': 'file_name'},
 'grid_scan_params': {'dwell_time': 0.2,
                      'x_start': 0.0,
                      'x_step_size': 0.1,
                      'x_steps': 5,
                      'y1_start': 0.0,
                      'y_step_size': 0.1,
                      'y_steps': 10,
                      'z1_start': 0.0},
 'use_roi': False}
 ```

 Any of the above parameters can be excluded and the above values will be used instead.

Getting the Runner Status
------------------------

To get the status of the runner:
```
curl http://127.0.0.1:5000/fast_grid_scan/status
```

Stopping the Scan
-----------------

To stop a scan that is currently running:
```
curl -X PUT http://127.0.0.1:5000/fast_grid_scan/stop
```