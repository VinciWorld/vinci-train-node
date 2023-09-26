FROM python:3.9.6-slim-buster

ENV PYTHONNUNBUFFERED 1
ENV PATH="/root/.local/bin:$PATH"
ENV PYTHONPATH='./'

WORKDIR /usr/src

RUN chmod a+w /usr/src

COPY ./app /usr/src/app
COPY ./.env /usr/src/
COPY ./poetry.lock /usr/src/poetry.lock
COPY ./pyproject.toml /usr/src/pyproject.toml
COPY ./logging.conf /usr/src/logging.conf
COPY ./unity /usr/src/unity



RUN apt-get update -y && apt-get install curl -y \
&& curl -sSL https://install.python-poetry.org | python3 - \
&& poetry config virtualenvs.create false \
&& poetry config installer.max-workers 10 \
&& poetry install \
&& apt-get remove curl -y
