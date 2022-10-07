#!/bin/bash

# controls_dev sets pip up to look at a local pypi server, which is incomplete

echo "Note: The current diamond pipenv installation is unable to lock with python 3.10."
echo "      If you want to lock then install your own recent pipenv version"

module unload controls_dev 

module load python/3.10

pipenv --rm

if [ ! -d "./.venv" ]
then
    mkdir ./.venv
fi

pipenv install --dev --python python

pipenv run pre-commit install

pipenv run tests
