# python-artemis

Repository for the Artemis project to implement "3D grid scans" using the BlueSky / Ophyd framework from BNL. 

https://nsls-ii.github.io/bluesky/


Development Installation
=================

1. Clone this project 
1. Run `dls_dev_env.sh` (This assumes you're on a DLS machine, if you are not you sould be able to just run a subset of this script)

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

Prometheus Metrics
==================
It a development state. 

To be able to see scraped metrics run `setup_metrics.sh`. This will build a prometheus image and run the container on host network `localhost:12201`. Navigate there to search and view metrics.

Currently the only metric is a test metric called `fgs_duration`. This will only populate once a scan has been triggered as it is pretending to time the duration of `get_plan`. It is a summary metric of the time take to execute a dummy `timing_test` function within `get_plan`.

This metric consists of two series, a count and a sum, which can be search in the prometheus web gui with `fgs_duration_count` and `fgs_duration_sum` respectively.

It is currently has only the instance and job labels (default for prometheus metrics).

System tests
============
Currently to run against s03 the flask app port needs to be changed as the eiger control uses 5000 and this interferes (it also uses 5001 and 5002).