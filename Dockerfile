#FROM nvidia/cuda:12.2.2-runtime-ubuntu22.04
#FROM  nvidia/cuda:12.2.2-cudnn8-runtime-ubuntu22.04
FROM nvidia/cuda:12.2.2-base-ubuntu22.04


ENV PYTHONUNBUFFERED 1
ENV PATH="/usr/local/nvidia/bin:/usr/local/cuda/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/root/.local/bin:/root/.pyenv/bin"
ENV PYTHONPATH='./'
ENV TZ=UTC

WORKDIR /usr/src

RUN chmod a+w /usr/src

COPY ./app /usr/src/app
COPY ./.env /usr/src/
COPY ./pyproject.toml /usr/src/pyproject.toml
COPY ./logging.conf /usr/src/logging.conf
COPY ./unity /usr/src/unity
COPY ./.python-version /usr/src/.python-version

ENV DEBIAN_FRONTEND=noninteractive

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Install pyenv dependencies
RUN apt-get update -y && apt-get install -y \
    git \
    python3-openssl \
    curl \
    zlib1g-dev \
    build-essential \
    libssl-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    wget \
    llvm \
    libncurses5-dev \
    libncursesw5-dev \
    xz-utils \
    tk-dev \
    libffi-dev \
    liblzma-dev \
    libgdbm-dev

# Install pyenv
RUN curl https://pyenv.run | bash

ENV PYENV_ROOT="/root/.pyenv"
ENV PATH="$PYENV_ROOT/bin:$PATH"

RUN pyenv install 3.10.1
RUN pyenv global 3.10.1

RUN eval "$(pyenv init --path)"


RUN python3.10 --version

COPY ./poetry.lock /usr/src/poetry.lock
COPY ./pyproject.toml /usr/src/pyproject.toml

RUN ls -l

ENV POETRY_REQUESTS_TIMEOUT=60

RUN echo "Current PATH: $PATH"
RUN nvidia-smi

RUN apt-get update -y && apt-get install -y curl \
    && curl -sSL https://install.python-poetry.org | python3.10 - --version 1.6.1 \
    && poetry config virtualenvs.create false \
    && poetry config installer.max-workers 10 \
    && poetry install \
    && apt-get remove curl -y
