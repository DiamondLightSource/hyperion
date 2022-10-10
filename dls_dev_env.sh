#!/bin/bash

# controls_dev sets pip up to look at a local pypi server, which is incomplete
module unload controls_dev 

module load python/3.10

mkdir .venv

python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]

pytest src/artemis/tests
