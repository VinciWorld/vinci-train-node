from functools import lru_cache
import json
import logging
import threading
import time
import uuid
from anyio import sleep
import pika
from typing import Callable
from app.settings.settings import Environments, settings, rabbitmq_settings
from app.domains.train_model.schemas.constants import TrainJobInstanceStatus

from app.domains.train_model.schemas.train_queue import TrainJobQueue

logger = logging.getLogger(__name__) 


class RabbitMQClient:
    def __init__(self, connection: pika.BlockingConnection):
        self.connection = connection
        self.train_job_channel = self.connection.channel()
        self.consume_train_jobs_channel = self.connection.channel()
        self.train_job_status_update_channel = self.connection.channel()  # Create a separate channel for status updates
        self.is_consuming = True

        self.train_job_channel.basic_qos(prefetch_count=1)
        self.consume_train_jobs_channel.basic_qos(prefetch_count=1)
        self.train_job_status_update_channel.basic_qos(prefetch_count=1)  # Set QoS for the status update channel
        
        self.train_job_lock = threading.Lock()
        self.train_job_status_uptade_lock = threading.Lock()
        self.consume_jobs_lock = threading.Lock()

        self.running_jobs_count = 0
        
        try:
            self.train_job_channel.queue_declare(queue='jobs', durable=True, arguments={'x-max-priority': 5})
            self.train_job_status_update_channel.queue_declare(queue='train_job_status_update', durable=True)  # Use the separate channel to declare the queue
        except pika.exceptions.ChannelClosedByBroker as e:
            logging.error(f"Failed to declare queue: {e}")
            raise

    def enqueue_job(self, job_data: 'TrainJobQueue', priority: int):
        job_json = job_data.model_dump_json()
        with self.train_job_lock:
            self.train_job_channel.basic_publish(
                exchange='',
                routing_key='jobs',
                body=job_json,
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    priority=priority
                )
            )

    def enqueue_train_job_status_update(self, run_id: uuid.UUID, status: 'TrainJobInstanceStatus'):
        status_update = {
            'run_id': str(run_id),
            'status': status.value
        }

        with self.train_job_status_uptade_lock:
            self.train_job_status_update_channel.basic_publish(  # Use the separate channel to publish the message
                exchange='',
                routing_key='train_job_status_update',
                body=json.dumps(status_update),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                )
            )

    def dequeue_job(self):
        with self.train_job_lock:
            method_frame, header_frame, body = self.consume_train_jobs_channel.basic_get(queue='jobs', auto_ack=False)

            if method_frame:
                delivery_tag = method_frame.delivery_tag
                job_data = json.loads(body.decode('utf-8'))
                return job_data, delivery_tag
            else:
                return None

    def consume_jobs(self, callback: Callable):
        thread = threading.Thread(target=self._process_data_events, args=(callback, 'jobs'))
        thread.setDaemon(True)
        thread.start()

    def _process_data_events(self, callback, queue_name):
        self.consume_train_jobs_channel.basic_consume(queue=queue_name, on_message_callback=callback)
        logging.info(f"Start consuming {queue_name}")
        while self.is_consuming:

            if self.running_jobs_count >= settings.max_jobs:
                logger.info(f"Max jobs {settings.max_jobs} instances! instance running: {self.running_jobs_count}")
                time.sleep(2)
            else:
                with self.train_job_lock:
                    self.consume_train_jobs_channel.connection.process_data_events()
                time.sleep(1)  # Add sleep to reduce CPU usage

        logging.info(f"Stop consuming {queue_name}")

    def acknowledge_job_sucess(self, delivery_tag):
        logger.info(f"tag: {delivery_tag}")
        with self.train_job_lock:
            self.consume_train_jobs_channel.basic_ack(delivery_tag=delivery_tag)
        logger.info(f"confirmed tag: {delivery_tag}")

    # the job is failed and is removed from the queue
    def acknowledge_job_failed(self, delivery_tag):
        logger.info(f"tag: {delivery_tag}")
        with self.train_job_lock:
            self.consume_train_jobs_channel.basic_nack(delivery_tag=delivery_tag, requeue=False)
        logger.info(f"failed tag: {delivery_tag}")

    # Use when the job failed and want to set to the queue again
    def acknowledge_job_failed_and_requeue(self, delivery_tag):
        logger.info(f"tag: {delivery_tag}")
        with self.train_job_lock:
            self.consume_train_jobs_channel.basic_reject(delivery_tag=delivery_tag, requeue=True)
        logger.info(f"rejected tag: {delivery_tag}")

        def close(self):
            with self.train_job_lock:
                self.is_consuming = False

@lru_cache
def get_rabbitmq_client() -> RabbitMQClient:
    
    if settings.env == Environments.LOCAL:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host="rabbitmq"))
        return RabbitMQClient(connection)

    else:

        parameters = pika.URLParameters(rabbitmq_settings.url)
        parameters.ssl_options = pika.SSLOptions(context=rabbitmq_settings.ssl_context)

        connection = pika.BlockingConnection(parameters)
        return RabbitMQClient(connection) 