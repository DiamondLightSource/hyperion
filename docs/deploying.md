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

* From a development hyperion workspace
```commandline
python utility_scripts/deploy/deploy_hyperion.py --kubernetes <beamline>
cd <path to deployed hyperion folder in /dls_sw>
./utility_scripts/deploy/deploy_to_k8s.sh --beamline=<beamline> hyperion
```

This will create a helm release "hyperion". The source folders will be mounted as 
bind mounts to allow the pod to pick up changes in production. For production these are expected to be in the normal 
place defined in `values.yaml`.

### development deployment


From a development `hyperion` workspace, either with a release image or using a development image built with the script 
above, you install a dev deployment to the cluster you are currently logged into with `kubectl`:

```commandline
./utility_scripts/deploy/deploy_to_k8s.sh --dev --beamline=<beamline> --repository=<your image repo> hyperion-test
```

The dev deployment bind-mounts the current `hyperion` workspace and `../dodal` into the container so that you can 
run against your own development code. **Clusters do not allow bind mounts from arbitrary directories so 
your workspace will have to be in a permitted directory such as your home directory.**

Please note, the deployment script is intended to be run from a checked-out matching version of the git repository.

`helm list` should then show details of the installed release 
