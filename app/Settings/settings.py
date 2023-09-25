from enum import Enum
import ssl
import uuid
from pathlib import Path
from pydantic_settings import BaseSettings

from decouple import config

ENV: str = config('ENV', default="local")
NODE_ID: str = config('NODE_ID')
NODE_DOMAIN: str = config('NODE_DOMAIN')
FASTAPI_HOST: str = config('FASTAPI_HOST', default="127.0.0.1")
FASTAPI_PORT: int = config('FASTAPI_PORT', default=8000)
RABBITMQ_USER=config('RABBITMQ_USER')
RABBITMQ_PASSWORD=config('RABBITMQ_PASSWORD')
RABBITMQ_HOST=config('RABBITMQ_HOST')
RABBITMQ_PORT=config('RABBITMQ_PORT')


ROOT_DIR = Path(__file__).parent.parent.parent



class Environments(str, Enum):
    LOCAL = "local"
    DEV = "dev"
    PROD = "prod"

class BaseConfig(BaseSettings):
    root_dir: Path = ROOT_DIR

    env: str = ENV
    node_id: uuid.UUID = NODE_ID
    node_domain: str = NODE_DOMAIN
    fastapi_host: str = FASTAPI_HOST
    fast_api_port: str = FASTAPI_PORT
    rabbitmq_user: str = RABBITMQ_USER
    rabbitmq_password: str = RABBITMQ_PASSWORD
    rabbitmq_host: str = RABBITMQ_HOST
    rabbitmq_port: str = RABBITMQ_PORT
    s3_bucket: str = ""

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