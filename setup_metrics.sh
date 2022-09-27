# build prometheus image
podman build ./metrics --format docker -t artemis-metrics:dev

# Run container with prometheus on port 12201
podman run --net host localhost/artemis-metrics:dev --web.listen-address="0.0.0.0:12201"