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

Starting a scan
--------------

To start a scan you can do the following:
```
curl -X PUT http://127.0.0.1:5003/fast_grid_scan/start --data-binary "@test_parameters.json" -H "Content-Type: application/json"
```

Getting the Runner Status
------------------------

To get the status of the runner:
```
curl http://127.0.0.1:5003/fast_grid_scan/status
```

Stopping the Scan
-----------------

To stop a scan that is currently running:
```
curl -X PUT http://127.0.0.1:5003/fast_grid_scan/stop

```


For running local dev logging
------------------------------
For development logs a local instance of graylog is needed. This needs to be run with both a mongo and elastic search instance. To set this up and run up the containers on your local machine run the `setup_graylog.sh` script.

This uses the generic defaults for a local graylog instance. It can be accessed on `localhost:9000` where the username and password for the graylog portal are both admin. To run artemis in this mode use the `--dev` flag with the run command.

You can also choose the logging level, like:
```
pipenv run artemis --dev --logging-level DEBUG
```
Without these flags the default behaviour will log to production graylog logs (not yet) with a logging level of INFO.
