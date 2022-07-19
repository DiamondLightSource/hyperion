#!/bin/bash

# Params - 2 semver strings of the form 1.11.2.3
# Returns - 0 if equal version, 1 if 1st param is a greater version number, 2 if 2nd param has greater version number
checkver () {
    if [[ $1 == $2 ]]
    then
        return 0
    fi
    local IFS=.
    local i ver1=($1) ver2=($2)
    for ((i=${#ver1[@]}; i<${#ver2[@]}; i++))
    do
        ver1[i]=0
    done
    for ((i=0; i<${#ver1[@]}; i++))
    do
        if [[ -z ${ver2[i]} ]]
        then
            ver2[i]=0
        fi
        if ((10#${ver1[i]} > 10#${ver2[i]}))
        then
            return 1
        fi
        if ((10#${ver1[i]} < 10#${ver2[i]}))
        then
            return 2
        fi
    done
    return 0
}

STOP=0
START=1
DEPLOY=0
for option in "$@"; do
    case $option in
        -b=*|--beamline=*)
            BEAMLINE="${option#*=}"
            shift
            ;;
        -v=*|--version=*)
            VERSION="${option#*=}"
            shift
            ;;
        --stop)
            STOP=1
            ;;
        --no-start)
            START=0
            ;;
        --deploy)
            DEPLOY=1
            ;;
        --help|--info)
            echo "Options"
            echo "  -b, --beamline=BEAMLINE Overrides the BEAMLINE environment variable with the given beamline"
            echo "  -v, --version=VERSION   Specifies the artemis version number to deploy. Option should be given in the form 0.0.0.0"
            echo "                          Will check git tags and use the lastest version as a default if no version is specified."
            echo "                          Unused outside of deploy operation."
            echo " "
            echo "Operations"
            echo "  --stop                  Used to stop a currently running instance of Artemis. Will override any other operations"
            echo "                          options"
            echo "  --deploy                Used to update and install a new version of Artemis."
            echo "  --no-start              Used to specify that the script should be run without starting the server."
            echo " "
            echo "By default this script will start an Artemis server unless the --no-start flag is specified."
            exit 0
            ;;
        -*|--*)
            echo "Unknown option ${option}. Use --help for info on option usage."
            exit 1
            ;;
    esac
done

if [[ -z "${BEAMLINE}" ]]; then
    echo "BEAMLINE parameter not set. Use the option -b, --beamline=BEAMLNE to set it manually"
    exit 1
fi

SSH_KEY_FILE_LOC="/dls_sw/${BEAMLINE}/software/gda_versions/var/.ssh/${BEAMLINE}-ssh.key"

if [[ $STOP == 1 ]]; then
    STOP_STRING="pkill -f src/artemis/main.py"
    if [[ $HOSTNAME != "${BEAMLINE}-control@diamond.ac.uk" ]]; then
        ssh -T -o BatchMode=yes -i ${SSH_KEY_FILE_LOC} ${BEAMLINE}-control.diamond.ac.uk ${STOP_STRING}
        exit 0
    fi
    eval ${STOP_STRING}
    exit 0
fi

ARTEMIS_PATH="/dls_sw/${BEAMLINE}/software/artemis"

if [[ -d "${ARTEMIS_PATH}" ]]; then
    cd ${ARTEMIS_PATH}
else
    echo "Couldn't find artemis installation at ${ARTEMIS_PATH} terminating script"
    exit 1
fi



if [[ $DEPLOY == 1 ]]; then
    echo "Fetching artemis remote repository"
    git fetch --all --tags --prune
    if [[ -z "${VERSION}" ]]; then
        echo "No verison number specified, finding latest version tag"
        VERSION="0"
        for version_tag in $(git ls-remote --tags origin/main); do
            checkver $VERSION ${version_tag}
            case $? in
                0|1) ;; # do nothing if VERSION is still the latest version
                2) VERSION = ${version_tag} ;;
            esac
        done
        echo "Found version ${VERSION}"
    fi

    git checkout "tags/${VERSION}"

    module unload controls_dev
    module load python/3.10

    pipenv install --python 3.10

    sleep 1
    echo "Version ${VERSION} of artemis finished installing"
fi

if [[ $START == 1 ]]; then
    COMMAND_STRING="source ${ARTEMIS_PATH}/start_artemis.sh ${ARTEMIS_PATH} ${BEAMLINE}"
    echo "running ${COMMAND_STRING} on control machine"

    if [[ $HOSTNAME != "${BEAMLINE}-control@diamond.ac.uk" || $USERNAME != "gda2" ]]; then
        ssh -T -o BatchMode=yes -i ${SSH_KEY_FILE_LOC} gda2@${BEAMLINE}-control.diamond.ac.uk ${COMMAND_STRING}
    else
        eval $COMMAND_STRING
    fi
    sleep 1
    echo "Artemis Server Started"
fi
