#!/bin/bash

echo "$(date +'%d/%m/%Y %T') Running start_artemis.sh script on $HOSTNAME with user $USER" >> bashlog.txt

ARTEMIS_PATH="/dls_sw/${BEAMLINE}/software/artemis"

cd ${ARTEMIS_PATH}

#if [[ -z $(pgrep -f src/artemis/main.py) ]]; then
pkill -f src/artemis/main.py
#fi

module unload controls_dev
module load python/3.10
module load dials

ISPYB_CONFIG_PATH="/dls_sw/dasc/mariadb/credentials/ispyb-artemis-${BEAMLINE}.cfg"

export ISPYB_CONFIG_PATH

pipenv run python src/artemis/main.py &

sleep 2
