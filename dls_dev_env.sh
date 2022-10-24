#!/bin/bash

# controls_dev sets pip up to look at a local pypi server, which is incomplete
module unload controls_dev 

module load python/3.10

if [[ -d "./.venv" ]]
then
    pipenv --rm
fi

mkdir .venv

pipenv install --dev

pipenv run pre-commit install

pipenv run tests