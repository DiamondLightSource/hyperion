# python-artemis

Repository for the Artemis project to implement "3D grid scans" using the BlueSky / Ophyd framework from BNL. 

https://nsls-ii.github.io/bluesky/


Development Installation
=================

1. Clone this project 
1. If on a DLS machine avoid the controls pypi server and get Python 3.10 by running:
    ```
    module unload controls_dev
    module load python/3.10
    ```
    If not at DLS, use your local version of Python 3.10
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
pipenv run main
```

Starting a plan
--------------

To start a scan:
```
curl -X PUT http://127.0.0.1:5000/fast_grid_scan/start --data-binary "@test_parameters.json" -H "Content-Type: application/json"
```

To start a flux calculation:
```
curl -X PUT http://127.0.0.1:5000/flux_calculation/start --data-binary "@test_flux_calculation_parameters.json" -H "Content-Type: application/json"
```

To start a flux prediction:
```
curl -X PUT http://127.0.0.1:5000/flux_prediction/start --data-binary "@test_flux_prediction_parameters.json" -H "Content-Type: application/json"
```

Getting the Runner Status
------------------------

To get the status of the runner:
```
curl http://127.0.0.1:5000/<plan_name>/status
```
Where `<plan_name>` is one of `fast_grid_scan`, `flux_calculation`, or `flux_prediction`.

Stopping a plan
-----------------

To stop a scan that is currently running:
```
curl -X PUT http://127.0.0.1:5000/<plan_name>/stop
```
Where `<plan_name>` is one of `fast_grid_scan`, `flux_calculation`, or `flux_prediction`.