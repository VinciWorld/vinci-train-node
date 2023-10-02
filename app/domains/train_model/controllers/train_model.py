import asyncio
import json
import logging
import threading
import uuid
from anyio import Event

import websockets

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
from app.clients.rabbitmq_client import RabbitMQClient, get_rabbitmq_client
from app.clients.redis_client import RedisClient, get_redis_client
from app.domains.train_model.schemas.constants import TrainJobInstanceStatus
from app.domains.train_model.services.train_model import TrainModelService



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


@train_model_router.websocket("/train-instance-stream")
async def ws_train_instance_stream(
    ws_node: WebSocket,
    redis_client: RedisClient = Depends(get_redis_client),
    rabbitmq_client: RabbitMQClient = Depends(get_rabbitmq_client)
):
    await ws_node.accept()
    logger.info(f"Accept")

    ws_central = None
    try:
        data = await ws_node.receive_text()

        logger.info(f"Welcome data: {data}")

        train_job_instance = redis_client.retrieve_current_train_job()
        delivery_tag = redis_client.get_delivery_tag(train_job_instance.run_id)
        if train_job_instance:
            central_node_url = train_job_instance.central_node_url
            logger.info(f"Connecting central node: {central_node_url}")
            async with websockets.connect(f"ws://{central_node_url}/ws/v1/train-node-stream") as ws_central:
                logger.info(f"Connected to central node: {central_node_url}")
                data = {
                         "run_id": str(train_job_instance.run_id)
                }
                logger.info(f"State: {ws_node.client_state}")
                await ws_central.send(json.dumps(data))

                rabbitmq_client.acknowledge_job(delivery_tag)
                rabbitmq_client.enqueue_train_job_status_update(
                    train_job_instance.run_id, TrainJobInstanceStatus.RUNNING
                )

                stop_event = Event()
                ws_central_lock = asyncio.Lock()
                asyncio.create_task(
                        send_metrics_data_to_central_node(
                        train_job_instance.run_id,
                        ws_central,
                        redis_client,
                        stop_event,
                        ws_central_lock
                    )
                )

                try:
                    while ws_node.client_state == WebSocketState.CONNECTED:
                        data = await ws_node.receive_text()
                        #logger.info(f"******{data}")
                        async with ws_central_lock:
                            await ws_central.send(data)

                except WebSocketDisconnect as e:
                    logger.info(f"WebSocketDisconnect: {e}")
                    raise
        
    except Exception as e:
        logger.info(f"Failed ERROR: {e}")
    finally:
        try:
            stop_event.set() 
            await ws_node.close()
            logger.info(f"Closed")
        except Exception as e:
            logger.error(f"Error closing train Node WebSocket: {e}")

        try:
            if ws_central:
                await ws_central.close()
                logger.info(f"Central WebSocket closed")
        except Exception as e:
            logger.error(f"Error closing central Node WebSocket: {e}")




async def send_metrics_data_to_central_node(
        run_id: uuid.UUID,
        ws_central: WebSocket,
        redis_client: RedisClient,
        stop_event: Event,
        ws_central_lock: asyncio.Lock
):

    while not stop_event.is_set():
        metrics_json = redis_client.pop_log_metrics(run_id) 
        if metrics_json:
            async with ws_central_lock:
                logger.info(f"metrics_json: {metrics_json}")
                await ws_central.send(metrics_json)
        await asyncio.sleep(0.1)



@train_model_router.on_event("shutdown")
def on_train_model_shutdown():
    pass