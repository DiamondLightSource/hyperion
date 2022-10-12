#!/bin/bash

# For setting up a new pipenv and locking. Without installing a newer version of pipenv using pip,
# pipenv will default to version 2021.5.29 which is incompatible with python/3.10 for generating a new
# Pipfile.lock

module unload controls_dev
module load python/3.10

echo "--- installing latest version of pipenv"
pip install pipenv --user


echo "--- removing present virtual env"
$HOME/.local/bin/pipenv --rm
if [ ! -d "./.venv" ]
then
    mkdir ./.venv
fi

if [ -f "./Pipfile.lock" ]
then
  echo "--- Pipfile.lock already present, deleting now"
  rm ./Pipfile.lock
fi

echo "--- setting up new environment"
$HOME/.local/bin/pipenv --python python
$HOME/.local/bin/pipenv install --dev


pipenv run tests
pipenv run pre-commit install
