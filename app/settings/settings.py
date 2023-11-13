from enum import Enum
import ssl
from typing import Type
import uuid
from pathlib import Path
from pydantic_settings import BaseSettings

from decouple import config

ENV: str = config('ENV', default="local")
SECURE_CONNECTION: bool = config('SECURE_CONNECTION', default=False, cast=bool)
NODE_ID: str = config('NODE_ID')
NODE_DOMAIN: str = config('NODE_DOMAIN')
FASTAPI_HOST: str = config('FASTAPI_HOST', default="127.0.0.1")
FASTAPI_PORT: int = config('FASTAPI_PORT', default=8000)
RABBITMQ_USER=config('RABBITMQ_USER')
RABBITMQ_PASSWORD=config('RABBITMQ_PASSWORD')
RABBITMQ_HOST=config('RABBITMQ_HOST')
RABBITMQ_PORT=config('RABBITMQ_PORT')
MAX_JOBS = config('MAX_JOBS')
RUNNER_ID: str = config('RUNNER_ID', default="unknown-runner")


ROOT_DIR = Path(__file__).parent.parent.parent


UNITY_DIR_RESULTS = ROOT_DIR / 'results'
UNITY_DIR_RUNS = UNITY_DIR_RESULTS / 'run_logs'
UNITY_EVNS_DIR = ROOT_DIR / 'unity' / 'unity_envs'
UNITY_BEHAVIORS_DIR = ROOT_DIR / 'unity' / 'behaviors'

class Environments(str, Enum):
    LOCAL = "local"
    DEV = "dev"
    PROD = "prod"

class BaseConfig(BaseSettings):
    root_dir: Path = ROOT_DIR
    unity_reults: Path = UNITY_DIR_RESULTS
    unity_envs_dir: Path = UNITY_EVNS_DIR
    unity_behaviors_dir: Path = UNITY_BEHAVIORS_DIR
    env: str = ENV
    node_id: uuid.UUID = NODE_ID
    node_domain: str = NODE_DOMAIN
    fastapi_host: str = FASTAPI_HOST
    fast_api_port: str = FASTAPI_PORT
    rabbitmq_user: str = RABBITMQ_USER
    rabbitmq_password: str = RABBITMQ_PASSWORD
    rabbitmq_host: str = RABBITMQ_HOST
    rabbitmq_port: str = RABBITMQ_PORT
    runner_id: str = RUNNER_ID
    s3_bucket: str = ""
    max_jobs: int = MAX_JOBS
    http_prefix: str = "https" if SECURE_CONNECTION else "http"
    ws_prefix: str = "wss" if SECURE_CONNECTION else "ws"

class Settings(BaseConfig):
    pass

settings = Settings()

class RabbitMQClientSettings():
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    ssl_context.set_ciphers('ECDHE+AESGCM:!ECDSA')
    url = f"amqps://{settings.rabbitmq_user}:{settings.rabbitmq_password}@{settings.rabbitmq_host}:{settings.rabbitmq_port}"

    class Confg:
        env_file_encoding= "utf-8"

rabbitmq_settings = RabbitMQClientSettings()