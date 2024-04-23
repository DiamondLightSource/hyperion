FROM python:3.11 AS build
ADD . /project/
WORKDIR "/project"
RUN pip install -e .[dev]
RUN python -m build