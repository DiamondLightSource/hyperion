#!/bin/bash
function cleanup()
{
    pkill -f rabbitmq
    rm -rf /home/$USER/.zocalo/*
    echo "May take some seconds for zocalo to die, do not immediately try and restart"
}

trap cleanup EXIT

# kills the gda dummy activemq, that takes the port for rabbitmq
module load dasctools
activemq-for-dummy stop

# starts the rabbitmq server and generates some credentials in ~/.fake_zocalo
module load rabbitmq/dev

# allows the `dev_hyperion` zocalo environment to be used
module load dials/latest

source .venv/bin/activate
python fake_zocalo/__main__.py
