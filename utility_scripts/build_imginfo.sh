#!/bin/bash
function help {
    cat <<END
`basename $0` [-p] <imginfo_git_workspace>
      Create and build imginfo in the specified directory
Options:
    -p use podman instead of docker
`basename $0` --help|-h
      This help
END
    exit 1
}

if [ -z "$1" ]; then
  help
fi

DOCKER=docker
case $1 in
  --help|-h)
    help
    ;;
  -p)
    DOCKER=podman
    shift
    ;;
  *)

esac
WORKDIR=$1
IMGINFO_TAG=9810b92
IMGINFO_GITHUB=git@github.com:githubgphl/imginfo.git
if [ -d ${WORKDIR} ]; then
        rm -rf ${WORKDIR}
fi
git clone ${IMGINFO_GITHUB} ${WORKDIR}
git checkout ${IMGINFO_TAG}
${DOCKER} build ${WORKDIR} --file ${WORKDIR}/Dockerfile --tag imginfo
