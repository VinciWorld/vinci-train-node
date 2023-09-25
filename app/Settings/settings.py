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
    s3_bucket: str = ""

class Settings(BaseConfig):
    pass

settings = Settings()
