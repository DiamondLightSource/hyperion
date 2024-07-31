FROM python:3.11 AS build
ADD . /project/
WORKDIR "/project"
RUN pip install -e .[dev]
RUN python -m build

ENTRYPOINT /project/utility_scripts/docker/entrypoint.sh

EXPOSE 5005