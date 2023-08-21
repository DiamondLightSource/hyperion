# hyperion
![Tests](https://github.com/DiamondLightSource/hyperion/actions/workflows/code.yml/badge.svg) [![codecov](https://codecov.io/gh/DiamondLightSource/hyperion/branch/main/graph/badge.svg?token=00Ww81MHe8)](https://codecov.io/gh/DiamondLightSource/hyperion)

Repository for the Hyperion project to implement "3D grid scans" using the BlueSky / Ophyd framework from BNL. 

https://nsls-ii.github.io/bluesky/


Development Installation
=================

Run `dls_dev_env.sh` (This assumes you're on a DLS machine. If you are not, you should be able to just run a subset of this script)

Note that because Hyperion makes heavy use of [Dodal](https://github.com/DiamondLightSource/dodal) this will also pull a local editable version of dodal to the parent folder of this repo.

Controlling the Gridscan Externally (e.g. from GDA)
=====================

Starting the bluesky runner
-------------------------
You can start the bluesky runner by running `run_hyperion.sh`. Note that this will fail on a developer machine unless you have a simulated beamline running, instead you should do `run_hyperion.sh --skip-startup-connection`, which will give you a running instance (note that without hardware trying to run a plan on this will fail).

This script will determine whether you are on a beamline or a production machine based on the `BEAMLINE` environment variable.  If on a beamline Hyperion will run with `INFO` level logging, sending its logs to both production graylog and to the beamline/log/bluesky/hyperion.txt on the shared file system.

If in a dev environment Hyperion will log to a local graylog instance instead and into a file at `./tmp/dev/hyperion.txt`. A local instance of graylog will need to be running for this to work correctly. To set this up and run up the containers on your local machine run the `setup_graylog.sh` script.

This uses the generic defaults for a local graylog instance. It can be accessed on `localhost:9000` where the username and password for the graylog portal are both admin.

The logging level of hyperion can be selected with the flag
```
python -m hyperion --dev --logging-level DEBUG
```

Additionally, `INFO` level logging of the Bluesky event documents can be enabled with the flag
```
python -m hyperion --dev --verbose-event-logging
```

Lastly, you can choose to skip running the hardware connection scripts on startup with the flag
```
python -m hyperion --skip-startup-connection
```

Testing
--------------
To be able to run the system tests, or a complete fake scan, we need the simulated S03 beamline. This can be found at: https://gitlab.diamond.ac.uk/controls/python3/s03_utils

To fake interaction and processing with Zocalo, you can run `fake_zocalo/dls_start_fake_zocalo.sh`, and make sure to run `module load dials/latest` before starting hyperion (in the same terminal).

Tracing
--------------

Tracing information (the time taken to complete different steps of experiments) is collected by an [OpenTelemetry](https://opentelemetry.io/) tracer, and currently we export this information to a local Jaeger monitor (if available). To see the tracing output, run the [Jaeger all-in-one container](https://www.jaegertracing.io/docs/1.6/getting-started/), and go to the web interface at http://localhost:16686. 


Starting a scan
--------------

To start a scan you can do the following:
```
curl -X PUT http://127.0.0.1:5005/flyscan_xray_centre/start --data-binary "@test_parameters.json" -H "Content-Type: application/json"
```

Getting the Runner Status
------------------------

To get the status of the runner:
```
curl http://127.0.0.1:5005/status
```

Stopping the Scan
-----------------

To stop a scan that is currently running:
```
curl -X PUT http://127.0.0.1:5005/stop

```

