#!/bin/bash

STOP=0
START=1
SKIP_STARTUP_CONNECTION=false
VERBOSE_EVENT_LOGGING=false
IN_DEV=false
EXTERNAL_CALLBACK_SERVICE=false
LOGGING_LEVEL="INFO"

for option in "$@"; do
    case $option in
        -b=*|--beamline=*)
            BEAMLINE="${option#*=}"
            shift
            ;;
        --stop)
            STOP=1
            ;;
        --no-start)
            START=0
            ;;
        --skip-startup-connection)
            SKIP_STARTUP_CONNECTION=true
            ;;
        --dev)
            IN_DEV=true
            ;;
        --verbose-event-logging)
            VERBOSE_EVENT_LOGGING=true
            ;;
        --external-callbacks)
            EXTERNAL_CALLBACK_SERVICE=true
            ;;
        --logging-level=*)
            LOGGING_LEVEL="${option#*=}"
            ;;

        --help|--info|--h)
        
        #Combine help from here and help from hyperion
            source .venv/bin/activate
            python -m hyperion --help
            echo "  -b, --beamline=BEAMLINE Overrides the BEAMLINE environment variable with the given beamline"
            echo " "
            echo "Operations"
            echo "  --stop                  Used to stop a currently running instance of Hyperion. Will override any other operations"
            echo "                          options"
            echo "  --no-start              Used to specify that the script should be run without starting the server."
            echo " "
            echo "By default this script will start an Hyperion server unless the --no-start flag is specified."
            exit 0
            ;;
        -*|--*)
            echo "Unknown option ${option}. Use --help for info on option usage."
            exit 1
            ;;
    esac
done

kill_active_apps () {
    echo "Killing active instances of hyperion and hyperion-callbacks..."
    pkill -e -f "python.*hyperion"
    echo "done."
}

check_user () {
    if [[ $HOSTNAME != "${BEAMLINE}-control.diamond.ac.uk" || $USER != "gda2" ]]; then
        echo "Must be run from beamline control machine as gda2"
        echo "Current host is $HOSTNAME and user is $USER"
        exit 1
    fi
}

#Check valid logging level was chosen
if [[ "$LOGGING_LEVEL" != "INFO" && "$LOGGING_LEVEL" != "CRITICAL" && "$LOGGING_LEVEL" != "ERROR" 
    && "$LOGGING_LEVEL" != "WARNING" && "$LOGGING_LEVEL" != "DEBUG" ]]; then
    echo "Invalid logging level selected, defaulting to INFO"
    LOGGING_LEVEL="INFO"
fi

if [ -z "${BEAMLINE}" ]; then
    echo "BEAMLINE parameter not set, assuming running on a dev machine."
    echo "If you would like to run not in dev use the option -b, --beamline=BEAMLNE to set it manually"
    IN_DEV=true
fi

if [[ $STOP == 1 ]]; then
    if [ $IN_DEV == false ]; then
        check_user
    fi
    kill_active_apps

    echo "Hyperion stopped"
    exit 0
fi

if [[ $START == 1 ]]; then
    if [ $IN_DEV == false ]; then
        check_user

        ISPYB_CONFIG_PATH="/dls_sw/dasc/mariadb/credentials/ispyb-artemis-${BEAMLINE}.cfg"
        export ISPYB_CONFIG_PATH

    fi

    kill_active_apps

    module unload controls_dev
    module load dials

    RELATIVE_SCRIPT_DIR=$( dirname -- "$0"; )
    cd ${RELATIVE_SCRIPT_DIR}

    if [ -z "$HYPERION_LOG_DIR" ]; then
        if [ $IN_DEV == true ]; then
            HYPERION_LOG_DIR=$RELATIVE_SCRIPT_DIR/tmp/dev
        else
            HYPERION_LOG_DIR=/dls_sw/$BEAMLINE/logs/bluesky
        fi
    fi
    echo "$(date) Logging to $HYPERION_LOG_DIR"
    export HYPERION_LOG_DIR
    mkdir -p $HYPERION_LOG_DIR
    start_log_path=$HYPERION_LOG_DIR/start_log.txt
    callback_start_log_path=$HYPERION_LOG_DIR/callback_start_log.txt

    source .venv/bin/activate

    #Add future arguments here
    declare -A h_only_args=(        ["SKIP_STARTUP_CONNECTION"]="$SKIP_STARTUP_CONNECTION"
                                    ["VERBOSE_EVENT_LOGGING"]="$VERBOSE_EVENT_LOGGING"
                                    ["EXTERNAL_CALLBACK_SERVICE"]="$EXTERNAL_CALLBACK_SERVICE" )
    declare -A h_only_arg_strings=( ["SKIP_STARTUP_CONNECTION"]="--skip-startup-connection"
                                    ["VERBOSE_EVENT_LOGGING"]="--verbose-event-logging"
                                    ["EXTERNAL_CALLBACK_SERVICE"]="--external-callbacks")

    declare -A h_and_cb_args(           ["IN_DEV"]="$IN_DEV"
                                        ["LOGGING_LEVEL"]="$LOGGING_LEVEL" )
    declare -A h_and_cb_arg_strings(    ["IN_DEV"]="--dev"
                                        ["LOGGING_LEVEL"]="--logging-level=$LOGGING_LEVEL" )

    h_commands=()
    for i in "${!h_only_args[@]}"
    do
        if [ "${h_only_args[$i]}" != false ]; then 
            h_commands+="${h_only_arg_strings[$i]} ";
        fi;
    done
    cb_commands=()
    for i in "${!h_and_cb_args[@]}"
    do
        if [ "${h_and_cb_args[$i]}" != false ]; then 
            h_commands+="${h_and_cb_arg_strings[$i]} ";
            cb_commands+="${h_and_cb_arg_strings[$i]} ";
        fi;
    done

    unset PYEPICS_LIBCA
    hyperion `echo $h_commands;`>$start_log_path 2>&1 &
    if [ $EXTERNAL_CALLBACK_SERVICE == true ]; then
        hyperion-callbacks `echo $cb_commands;`>$callback_start_log_path 2>&1 &
    fi

    echo "$(date) Waiting for Hyperion to boot"

    for i in {1..30}
    do
        echo "$(date)"
        curl --head -X GET http://localhost:5005/status >/dev/null
        ret_value=$?
        if [ $ret_value -ne 0 ]; then
            sleep 1
        else
            break
        fi
    done

    if [ $ret_value -ne 0 ]; then
        echo "$(date) Hyperion Failed to start!!!!"
        exit 1
    else
        echo "$(date) Hyperion started"
    fi
fi

sleep 1
