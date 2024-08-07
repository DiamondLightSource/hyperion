#!/bin/bash
# builds the docker image
BUILD=1
PUSH=1
for option in "$@"; do
    case $option in
        --no-build)
            BUILD=0
            shift
            ;;
        --no-push)
            PUSH=0
            shift
            ;;
        --help|--info|--h)
            CMD=`basename $0`
            echo "$CMD [options]"
            echo "Builds and/or pushes the docker container image to the repository"
            echo "  --help                  This help"
            echo "  --no-build              Do not build the image"
            echo "  --no-push               Do not push the image"
            exit 0
            ;;
        -*|--*)
            echo "Unknown option ${option}. Use --help for info on option usage."
            exit 1
            ;;
    esac
done

PROJECTDIR=`dirname $0`/..
VERSION=$1
if [ -z $VERSION ]; then
  python -m setuptools_scm --force-write-version-files
  VERSION=`hyperion --version | sed -e 's/[^a-zA-Z0-9._-]/_/g'`
fi
PROJECT=hyperion
TAG=$PROJECT:$VERSION
LATEST_TAG=$PROJECT:latest

if [[ $BUILD == 1 ]]; then
  echo "podman build --tag $TAG --tag $LATEST_TAG $PROJECTDIR"
  TMPDIR=/tmp podman build --tag $TAG --tag $LATEST_TAG $PROJECTDIR
fi

if [[ $PUSH == 1 ]]; then
  NAMESPACE=`podman login --get-login ghcr.io`
  if [[ $? != 0 ]]; then
    echo "Not logged in to ghcr.io"
    exit 1
  fi
  echo "Pushing to ghcr.io/$NAMESPACE/$PROJECT:latest ..."
  podman push $PROJECT:latest docker://ghcr.io/$NAMESPACE/$PROJECT:latest
  podman push $PROJECT:latest docker://ghcr.io/$NAMESPACE/$PROJECT:$VERSION
fi