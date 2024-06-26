#!/bin/bash
function help {
    cat <<END
Wrapper for imginfo
`basename $0` [-s] <master.h5>
      Run imginfo against the specified master file
Options:
	-s	Start an interactive shell instead of executing imginfo

Environment:
  DOCKER   set to 'podman' to use podman otherwise docker is the default

`basename $0` --help|-h
      This help
END
    exit 1
}

if [ -z "$1" ]; then
  help
fi

if [ -z "$DOCKER" ]; then
  DOCKER=docker
fi

while [ -n "$1" ] ; do
	case $1 in
	  --help|-h)
	    help
	    ;;
	  -s)
	    SHELL_MODE=1
	    shift;
	    ;;
	  *)
	    break
	    ;;
	esac
done
IMAGE_NAME=imginfo:latest

if ! ${DOCKER} image inspect ${IMAGE_NAME} > /dev/null; then
  echo "$DOCKER image ${IMAGE_NAME} does not exist."
  exit 2
fi

MASTER_FILE=`readlink -f $1`
PARENT_DIR=`dirname $MASTER_FILE`
MASTER_FILENAME=`basename $MASTER_FILE`
if [ -n "$SHELL_MODE" ]; then
	${DOCKER} run -t -i -v ${PARENT_DIR}:/data/:z ${IMAGE_NAME} /bin/bash
else
	${DOCKER} run -v ${PARENT_DIR}:/data/ ${IMAGE_NAME} ./imginfo /data/${MASTER_FILENAME}
fi
