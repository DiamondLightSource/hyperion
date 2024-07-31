Building the Docker image
====

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

Pushing the docker image
===

If building a release image, the image should be pushed to github by the release CI scripts _TODO_

If building a test image, the image should be pushed to your personal GH account:

`cat <mysecretfile> | podman login ghcr.io --username <your gh login> --password-stdin`
 
`podman push ghcr.io/<your gh login>/`

Deploying to kubernetes
===

Once the docker image is built, the image can be deployed to kubernetes using the `deploy_to_k8s.sh` script