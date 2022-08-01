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
pipenv run main
```

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