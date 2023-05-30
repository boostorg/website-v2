# syntax = docker/dockerfile:experimental

FROM python:3.11-slim AS builder-py

RUN apt update && apt install -y build-essential gcc python-dev libpq-dev postgresql-client ruby ruby-dev && rm -rf /var/lib/apt/lists/*

# Install Asciidoctor
RUN gem install asciidoctor

RUN pip install -U pip

COPY ./requirements.txt ./code/requirements.txt

RUN python3 -m venv /venv

RUN --mount=type=cache,target=/root/.cache \
    . /venv/bin/activate && \
    pip install -U pip && \
    pip install --no-compile -r /code/requirements.txt

FROM python:3.11-slim AS release

RUN apt update && apt install -y git libpq-dev ruby ruby-dev && rm -rf /var/lib/apt/lists/*

# Install Asciidoctor
RUN gem install asciidoctor

# Copy Asciidoctor binary from builder stage
COPY --from=builder-py /usr/local/bin/asciidoctor /usr/local/bin/

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

ARG TAG
ENV IMAGE_TAG=$TAG

LABEL Description="Boost.org" Vendor="REVSYS"
LABEL Version="${IMAGE_TAG}"
