# syntax = docker/dockerfile:experimental

FROM python:3.9-slim-buster AS builder-py

RUN apt-get update && apt-get install -y build-essential gcc python-dev postgresql-client && rm -rf /var/lib/apt/lists/*

RUN pip install -U pip

COPY ./requirements.txt ./code/requirements.txt

RUN python3 -m venv /venv

RUN --mount=type=cache,target=/root/.cache \
    . /venv/bin/activate && \
    pip install -U pip && \
    pip install --no-compile -r /code/requirements.txt

FROM python:3.9-slim-buster AS release

ENV PATH /venv/bin:/bin:/usr/bin:/usr/local/bin
ENV PYTHONDONTWRITEBYTECODE=true
ENV PYTHONPATH /code
ENV PYTHONUNBUFFERED 1
ENV PYTHONWARNINGS ignore

RUN mkdir /code

COPY --from=builder-py /venv/ /venv/
COPY --from=builder-py /code/ /code/
COPY . /code/

WORKDIR /code

CMD ["gunicorn", "-c", "/code/gunicorn.conf.py", "config.wsgi"]

ENV X_IMAGE_TAG v0.0.0

LABEL Description="Boost.org" Vendor="REVSYS"
LABEL Version="${X_IMAGE_TAG}"
