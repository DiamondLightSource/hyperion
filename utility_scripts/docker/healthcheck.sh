#!/bin/bash
# Healthcheck script for the container image
curl -f --head -X GET http://localhost:5005/status || exit 1
