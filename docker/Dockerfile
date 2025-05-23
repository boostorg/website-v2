# syntax = docker/dockerfile:experimental

FROM python:3.11-slim AS builder-py

ARG LOCAL_DEVELOPMENT

RUN apt update && apt install -y build-essential gcc python-dev-is-python3 libpq-dev postgresql-client ruby ruby-dev && rm -rf /var/lib/apt/lists/*

# Install ruby's asciidoctor.
RUN gem install asciidoctor

# Upgrade to the latest pip.
RUN pip install --upgrade pip

# Boostrap uv.
RUN pip install 'uv>=0.2.27,<0.3'
COPY ./requirements.txt ./code/requirements.txt
COPY ./requirements-dev.txt ./code/requirements-dev.txt


# Create the virtualenv.
RUN uv venv venv

# Activate the virtualenv and install the requirements.
RUN --mount=type=cache,target=/root/.cache \
    . /venv/bin/activate && \
    uv pip install -r /code/requirements.txt

RUN --mount=type=cache,target=/root/.cache if [ "${LOCAL_DEVELOPMENT}" = "true" ]; then \
      . /venv/bin/activate && \
      uv pip install -r /code/requirements-dev.txt; \
    fi


# Builder step for JS.
FROM node:22-slim AS builder-js

COPY . /code/
WORKDIR /code/
RUN yarn install
RUN yarn build


# Final image.
FROM python:3.11-slim AS release

RUN apt update && apt install -y git libpq-dev ruby ruby-dev && rm -rf /var/lib/apt/lists/*

# Install Asciidoctor
RUN gem install asciidoctor asciidoctor-boost

# Boostrap uv.
RUN pip install 'uv>=0.2.27,<0.3'

ENV PATH /venv/bin:/bin:/usr/bin:/usr/local/bin
ENV PYTHONDONTWRITEBYTECODE=true
ENV PYTHONPATH /code
ENV PYTHONUNBUFFERED 1
ENV PYTHONWARNINGS ignore

RUN mkdir /code

COPY --from=builder-py /venv/ /venv/
COPY --from=builder-py /code/ /code/
COPY . /code/
COPY --from=builder-js /code/static/css/styles.css /code/static/css/styles.css

WORKDIR /code

CMD ["gunicorn", "-c", "/code/gunicorn.conf.py", "config.wsgi"]

ARG TAG
ENV IMAGE_TAG=$TAG

LABEL Description="Boost.org" Vendor="REVSYS"
LABEL Version="${IMAGE_TAG}"
