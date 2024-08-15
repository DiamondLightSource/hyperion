FROM python:3.11 AS build
ADD . /app/hyperion
WORKDIR "/app/hyperion"
RUN pip install --no-cache-dir --no-compile -e .

# Check out and install dodal locally with no dependencies as this may be a different version to what
# is referred to in the setup.cfg, but we don't care as it will be overridden by bind mounts in the
# running container
RUN mkdir ../dodal && \
git clone https://github.com/DiamondLightSource/dodal.git ../dodal && \
pip install --no-cache-dir --no-compile --no-deps -e ../dodal

ENTRYPOINT /app/hyperion/utility_scripts/docker/entrypoint.sh

EXPOSE 5005