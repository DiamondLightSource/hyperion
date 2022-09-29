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
pipenv run artemis
```
The default behaviour of which is to run artemis with `INFO` level logging, sending its logs to both production graylog and to the beamline/log/bluesky/artemis.txt on the shared file system. 

To run locally in a dev environment use
```
pipenv run artemis --dev
```
This will log to a local graylog instance instead and into a file at `./tmp/dev/artemis.txt`. A local instance of graylog will need to be running for this to work correctly. To set this up and run up the containers on your local machine run the `setup_graylog.sh` script.

This uses the generic defaults for a local graylog instance. It can be accessed on `localhost:9000` where the username and password for the graylog portal are both admin.

The logging level of artemis can be selected with the flag
```
pipenv run artemis --dev --logging-level DEBUG
```

**DO NOT** run artemis at DEBUG level on production (without the --dev flag). This will flood graylog with messages and make people very grumpy.


Starting a scan
--------------

To start a scan you can do the following:
```
curl -X PUT http://127.0.0.1:5000/fast_grid_scan/start --data-binary "@test_parameters.json" -H "Content-Type: application/json"
```

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


System tests
============
Currently to run against s03 the flask app port needs to be changed as the eiger control uses 5000 and this interferes (it also uses 5001 and 5002).