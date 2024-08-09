#!/bin/bash
# Entry point for the production docker image that launches the external callbacks
# as well as the main server

for option in "$@"; do
    case $option in
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

        --help|--info|--h)
            echo "Arguments:"
            echo "  --dev start in development mode without external callbacks"
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
    pkill -e -f "SCREEN.*hyperion"
    echo "done."
}

RELATIVE_SCRIPT_DIR=$( dirname -- "$0"; )
cd ${RELATIVE_SCRIPT_DIR}

echo "$(date) Logging to $HYPERION_LOG_DIR"
mkdir -p $HYPERION_LOG_DIR
start_log_path=$HYPERION_LOG_DIR/start_log.log
callback_start_log_path=$HYPERION_LOG_DIR/callback_start_log.log

#Add future arguments here
declare -A h_only_args=(        ["SKIP_STARTUP_CONNECTION"]="$SKIP_STARTUP_CONNECTION"
                                ["VERBOSE_EVENT_LOGGING"]="$VERBOSE_EVENT_LOGGING"
                                ["EXTERNAL_CALLBACK_SERVICE"]="$EXTERNAL_CALLBACK_SERVICE" )
declare -A h_only_arg_strings=( ["SKIP_STARTUP_CONNECTION"]="--skip-startup-connection"
                                ["VERBOSE_EVENT_LOGGING"]="--verbose-event-logging"
                                ["EXTERNAL_CALLBACK_SERVICE"]="--external-callbacks")

declare -A h_and_cb_args=( ["IN_DEV"]="$IN_DEV" )
declare -A h_and_cb_arg_strings=( ["IN_DEV"]="--dev" )

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

trap kill_active_apps TERM 

if [ "$EXTERNAL_CALLBACK_SERVICE" = true ]; then
    hyperion-callbacks `echo $cb_commands;`>$callback_start_log_path 2>&1 &
fi

echo "$(date) Starting Hyperion..."
hyperion `echo $h_commands;`>$start_log_path  2>&1
