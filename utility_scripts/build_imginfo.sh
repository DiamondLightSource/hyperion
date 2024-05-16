#!/bin/bash
function help {
    cat <<END
`basename $0` [-p] <imginfo_git_workspace>
      Create and build imginfo in the specified directory
Options:
    -p use podman instead of docker
    -d build debug imginfo
`basename $0` --help|-h
      This help
END
    exit 1
}

if [ -z "$1" ]; then
  help
fi

DOCKER=docker
while [ -n "$1" ] ; do
	case $1 in
	  --help|-h)
	    help
	    ;;
	  -d)
	    DOCKERFILE=Dockerfile-imginfo-debug
	    shift
	    ;;
	  -p)
	    DOCKER=podman
	    shift
	    ;;
	  *)
	    break
	    ;;
	esac
done
if [ -z "$1" ]; then
	echo "workspace not specified"
	exit 1
fi

WORKDIR=$1
IMGINFO_TAG=9810b92
IMGINFO_GITHUB=git@github.com:githubgphl/imginfo.git
if [ -d ${WORKDIR} ]; then
        rm -r ${WORKDIR}
fi
git clone ${IMGINFO_GITHUB} ${WORKDIR}
git checkout ${IMGINFO_TAG}
if [ -z "$DOCKERFILE" ]; then
	DOCKERFILE=${WORKDIR}/Dockerfile
else
	DOCKERFILE=${WORKDIR}/${DOCKERFILE}
fi
${DOCKER} build ${WORKDIR} --file ${DOCKERFILE} --tag imginfo
