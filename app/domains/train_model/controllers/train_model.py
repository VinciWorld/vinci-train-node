import logging

from fastapi import APIRouter


logger = logging.getLogger(__name__) 

train_model_router = APIRouter(
    prefix='/api/v1',
    tags=["Train Model"]
)


@train_model_router.on_event("startup")
def on_train_model_router_startup():

    rabbitmq_client = get_rabbitmq_client()
    redis_client = get_redis_client()

    logger.info(f"on_train_model_router_startup")

    service = TrainModelService(redis_client, rabbitmq_client)
    threading.Thread(target=service.train_model, args=()).start()