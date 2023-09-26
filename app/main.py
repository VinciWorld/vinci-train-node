from fastapi import FastAPI
import logging

logging.config.fileConfig('logging.conf', disable_existing_loggers=False)  #type: ignore

app = FastAPI()


app.include_router(train_model_router)