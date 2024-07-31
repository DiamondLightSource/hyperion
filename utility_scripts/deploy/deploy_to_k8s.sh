#!/bin/bash
# Installs helm package to kubernetes
for option in "$@"; do
    case $option in
        -b=*|--beamline=*)
            BEAMLINE="${option#*=}"
            shift
            ;;
        --dev)
            DEV=true
            shift
            ;;
        --repository=*)
            REPOSITORY="${option#*=}"
            shift
            ;;
        --help|--info|--h)
            CMD=`basename $0`
            echo "$CMD [options] <release>"
            echo "Deploys hyperion to kubernetes"
            echo "  --help                  This help"
            echo "  --dev                   Install to a development kubernetes cluster (assumes project checked out under /home)"
            echo "  -b, --beamline=BEAMLINE Overrides the BEAMLINE environment variable with the given beamline"
            echo "  --repository=REPOSITORY Override the repository to fetch the image from"
            exit 0
            ;;
        -*|--*)
            echo "Unknown option ${option}. Use --help for info on option usage."
            exit 1
            ;;
    esac
done

if [[ -z $BEAMLINE ]]; then
  echo "BEAMLINE not set and -b not specified"
  exit 1
fi

RELEASE=$1

if [[ -z $RELEASE ]]; then
  echo "Release must be specified"
  exit 1
fi

HELM_OPTIONS=""
PROJECTDIR=$(readlink -e $(dirname $0)/../..)

if [[ -n $REPOSITORY ]]; then
  HELM_OPTIONS+="--set hyperion.imageRepository=$REPOSITORY "
fi

if [[ -n $DEV ]]; then
  GID=`id -g`
  SUPPLEMENTAL_GIDS=37904
  HELM_OPTIONS+="--set \
hyperion.dev=true,\
hyperion.runAsUser=$EUID,\
hyperion.runAsGroup=$GID,\
hyperion.supplementalGroups=[$SUPPLEMENTAL_GIDS],\
hyperion.logDir=/project/tmp,\
hyperion.projectDir=$PROJECTDIR \
--replace "
  mkdir -p $PROJECTDIR/tmp
fi

helm install $HELM_OPTIONS $RELEASE $PROJECTDIR/helmchart
