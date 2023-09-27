from fastapi import FastAPI
import logging

from app.domains.train_model.controllers.train_model import on_train_model_router_startup

logging.config.fileConfig('logging.conf', disable_existing_loggers=False)  #type: ignore

app = FastAPI()


app.include_router(on_train_model_router_startup)