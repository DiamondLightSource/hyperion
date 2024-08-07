Building the Docker image
====

Release builds of container images should be built by the github CI on release, ad-hoc builds can be performed via 
manual invocation of the Publish Docker Image workflow.

Development builds of container images can be made by running the `utility_scripts/build_docker_image.sh` script.
By default it will both build and push the image unless you specify `--no-build` or `--no-push`. To push an image you 
will first need to create a GH personal 
access token and then log in with podman as described below.

Pushing the docker image
===

If building a test image, the image should be pushed to your personal GH account:

`cat <mysecretfile> | podman login ghcr.io --username <your gh login> --password-stdin`

where `mysecretfile` contains your personal access token
 
`podman push ghcr.io/<your gh login>/`

Then run the `build_docker_image.sh` script.

## Troubleshooting

If you run into issues with `podman build .` failing with the error message
`io: read/write on closed pipe` then you may be running out of disk space - try setting TMPDIR environment variable

https://github.com/containers/podman/issues/22342

### Building image on ubuntu

If you run into issues such as 
```commandline
potentially insufficient UIDs or GIDs available in user namespace (requested 0:42 for /etc/gshadow): Check /etc/subuid and /etc/subgid: lchown /etc/gshadow: invalid argument
```

* Ensure newuidmap is installed
`sudo apt-get install uidmap`
* Add appropriate entries to `/etc/subuid` and `/etc/subgid`
e.g.
```
# subuid/subgid file
myuser:10000000:65536

# subuid/subgid file
myuser:10000000:65536
```
* kill any existing podman processes and retry

For further information, see https://github.com/containers/podman/issues/2542


Deploying to kubernetes
===

Once the docker image is built, the image can be deployed to kubernetes using the `deploy_to_k8s.sh` script

### Production deployment

* Check out the repo to a new folder
```commandline
cd /dls_sw/<beamline>/software/bluesky
git clone git@github.com:DiamondLightSource/hyperion.git hyperion_vX.Y.Z
``` 
* Recreate the `hyperion` symlink to point to the new folder
* ssh to the beamline control machine
* change user to the service account user
* cd to the new folder and run
```commandline
git checkout vX.Y.Z
./utility_scripts/deploy/deploy_to_k8s.sh hyperion
```

This will create a helm release "hyperion".

### development deployment

From your development workspace, either with a release image or using a development image built with :

```commandline
./utility_scripts/deploy/deploy_to_k8s.sh --dev --beamline=<beamline> --repository=<your image repo> hyperion-test
```

Please note, the deployment is intended to be run from a checked-out matching version of the git repository. For 
production this is expected to be in the normal place defined in `values.yaml`. The source folders will be mounted as 
bind mounts to allow the pod to pick up changes in production.

`helm list` should then show details of the installed release 
