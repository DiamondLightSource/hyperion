FROM python:3.10 AS build
ADD . /project/
WORKDIR "/project"
RUN pip install -e .[dev]
RUN python -m build