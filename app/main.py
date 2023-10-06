from fastapi import FastAPI
import logging
from app.logs.CloudWatchLogHandler import setup_cloudwatch_logging
from app.domains.train_model.controllers.train_model import train_model_router

logging.config.fileConfig('logging.conf', disable_existing_loggers=False)  #type: ignore
logging.info('Setting up cloudwatch logging')
setup_cloudwatch_logging()

app = FastAPI()

app.include_router(train_model_router)