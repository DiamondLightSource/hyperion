
# MAIN COMMANDS
setup:
	./dls_dev_env.sh

# note: complex and might not work https://stackoverflow.com/questions/13702425/source-command-not-found-in-sh-shell
env:
	. .venv/bin/activate

run-prod:
	./run_hyperion.sh

run-dev:
	./run_hyperion.sh --skip-startup-connection

# SCANS
scan-new:
	curl -X PUT http://127.0.0.1:5005/flyscan_xray_centre/start --data-binary "@tests/test_data/parameter_json_files/test_parameters.json" -H "Content-Type: application/json"

scan-status:

	curl http://127.0.0.1:5005/status

scan-stop:
	curl -X PUT http://127.0.0.1:5005/stop

# TESTING
test:
	python -m pytest -m "not s03" --random-order

test-debug:
	python -m pytest -m "not s03" --random-order -s --debug-logging


