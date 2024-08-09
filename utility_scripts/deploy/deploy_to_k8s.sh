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
        --appVersion=*)
            APP_VERSION="${option#*=}"
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
            echo "  --appVersion=version    Version of the image to fetch from the repository otherwise it is deduced
             from the setuptools_scm"
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

ensure_version_py() {
  # We require the _version.py to be created, this needs a minimal virtual environment
  if [[ ! -d $PROJECTDIR/.venv ]]; then
    echo "Creating _version.py"
    echo "Virtual environment not found - creating"
    module load python/3.11
    python -m venv $PROJECTDIR/.venv
    . $PROJECTDIR/.venv/bin/activate
    pip install setuptools_scm
  fi  
}

app_version() {
  ensure_version_py
  
  . $PROJECTDIR/.venv/bin/activate
  python -m setuptools_scm --force-write-version-files
}

if [[ -n $REPOSITORY ]]; then
  HELM_OPTIONS+="--set hyperion.imageRepository=$REPOSITORY "
fi

ensure_version_py
if [[ -z $APP_VERSION ]]; then
  APP_VERSION=$(app_version)
fi

if [[ -n $DEV ]]; then
  GID=`id -g`
  SUPPLEMENTAL_GIDS=37904
  HELM_OPTIONS+="--set \
hyperion.dev=true,\
hyperion.runAsUser=$EUID,\
hyperion.runAsGroup=$GID,\
hyperion.supplementalGroups=[$SUPPLEMENTAL_GIDS],\
hyperion.logDir=/app/hyperion/tmp "
  mkdir -p $PROJECTDIR/tmp
  DEPLOYMENT_DIR=$PROJECTDIR
else
  DEPLOYMENT_DIR=/dls_sw/i03/software/bluesky/hyperion_v${APP_VERSION}/hyperion
fi

HELM_OPTIONS+="--set hyperion.appVersion=$APP_VERSION,\
hyperion.projectDir=$DEPLOYMENT_DIR,\
dodal.projectDir=$DEPLOYMENT_DIR/../dodal " 

helm package $PROJECTDIR/helmchart --app-version $APP_VERSION
# Helm package generates a file suffixed with the chart version
helm upgrade --install $HELM_OPTIONS $RELEASE hyperion-0.0.1.tgz
