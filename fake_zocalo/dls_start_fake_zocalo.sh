#!/bin/bash

# kills the gda dummy activemq, that takes the port for rabbitmq
module load dasctools
activemq-for-dummy stop

# starts the rabbitmq server and generates some credentials in ~/.fake_zocalo
module load rabbitmq/dev

# allows the `dev_artemis` zocalo environment to be used
module load dials/latest

source .venv/bin/activate
python fake_zocalo/__main__.py