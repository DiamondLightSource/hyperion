#!/bin/bash

# Check we're in the right place
dir_name=${PWD##*/}
if [ "$dir_name" != "hyperion" ]; then
  echo "This script should be run from the 'hyperion' directory"
  exit 1
fi

# controls_dev sets pip up to look at a local pypi server, which is incomplete
module unload controls_dev 

module load python/3.10

if [ -d "./.venv" ]
then
rm -rf .venv
fi
mkdir .venv

python -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install wheel
pip install -e .[dev]

pre-commit install

# Ensure we use a local version of dodal
if [ ! -d "../dodal" ]; then
  git clone git@github.com:DiamondLightSource/dodal.git ../dodal
fi

pip install -e ../dodal[dev]

# get dlstbx into our env
ln -s /dls_sw/apps/dials/latest/latest/modules/dlstbx/src/dlstbx/ .venv/lib/python3.10/site-packages/dlstbx

pytest -m "not s03"
