from functools import partial
import logging
import os
import subprocess
import threading
import re

from app.clients.rabbitMQClient import RabbitMQClient, get_rabbitmq_client
from app.clients.redis_client import RedisClient
from app.domains.train_model.schemas.train_model import TrainJobInstance
from app.settings import settings
from app.domains.train_model.schemas.constants import TrainJobInstanceStatus
from app.domains.train_model.schemas.train_queue import TrainJobQueue

logger = logging.getLogger(__name__) 


class TrainModelService():
    def __init__(
            self,
            redis_client: RedisClient,
            rabbitmq_client: RabbitMQClient
    ):
        self.redis_client = redis_client
        self.rabbitmq_client = rabbitmq_client
        
    

    def train_model(
            self
    ) -> None:
        
        callback_with_shared_state = partial(
            _process_train_job,
            redis_client=self.redis_client
        )

        try:
            self.rabbitmq_client.consume_jobs(callback_with_shared_state)
        except Exception as e:
            logger.info(f"Rabbitmq stream connection lost: {e}")
  
        logger.info("Waitting for train jobs...")


def _process_train_job(
        channel,
        method,
        properties,
        body,
        redis_client: RedisClient
        ):
    
    rabbitmq_client = get_rabbitmq_client()

    train_job = TrainJobQueue.parse_raw(body.decode('utf-8'))
    train_job_instance = TrainJobInstance(
        **train_job.model_dump(),
        job_status=TrainJobInstanceStatus.RETRIEVED
    )
    redis_client.save_current_train_job_instance(train_job_instance)
    redis_client.save_run_status_and_delivery_tag(
        train_job_instance.run_id, TrainJobInstanceStatus.RETRIEVED.value, method.delivery_tag
    )
 
    logger.info(f"Launch Unity {train_job.run_id} tag: {method.delivery_tag}")
    #rabbitmq_client.acknowledge_job(method.delivery_tag)

    threading.Thread(
        target=_launch_unity_instante,
        args=(train_job_instance, redis_client, rabbitmq_client)
    ).start()

def _launch_unity_instante(
        train_job_instance: TrainJobInstance,
        redis_client: RedisClient,
        rabbitmq_client: RabbitMQClient
        ):
    logger.info("Preparing to launch Unity instance")

    run_id = train_job_instance.run_id

    run_path = settings.unity_runs / str(run_id)
    run_path.mkdir(parents=True, exist_ok=True)


    #TODO Save model config yml to be loaded by ML 

      
    job_count = redis_client.increment_trained_jobs_count()
    config_path = settings.unity_models_configs_dir / "hallway.yml"
    env_pah = settings.unity_envs_dir / "test-env.x86_64"
    port_suffix = str(job_count % 20)
    port = "500" + port_suffix
  
    os.chmod(env_pah, 0o777)

    cmd = (
        f"mlagents-learn {config_path} "
        f"--run-id {str(run_id)} "
        f"--force "
        f"--env {env_pah} " 
        f"--no-graphics "
        f"--base-port {port}"
    )
    rabbitmq_client.enqueue_train_job_status_update(
        train_job_instance.run_id, TrainJobInstanceStatus.STARTING
    )

    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
        logger.info(f"Unity instance Launched run_id: {run_id}")

        logger.info(os.getcwd())
        with open(f"unity/{run_id}-metrics.txt", mode="w", buffering=1) as file:
            while(True):
                retcode = p.poll() 
                line = p.stdout.readline() # type:ignore
                line = line.decode('utf-8')
                file.write(str(line))
                if retcode is not None:
                    logger.info(f"Unity instance terminated: {run_id}")
                    file.write("exit")
                    file.close()
                    break
    except Exception as e:
        logger.error(f"Unity instance Failed. ERROR: {e}")
        rabbitmq_client.enqueue_train_job_status_update(
            train_job_instance.run_id, TrainJobInstanceStatus.FAILED
        )
        return

    rabbitmq_client.enqueue_train_job_status_update(
        train_job_instance.run_id, TrainJobInstanceStatus.SUCCEEDED
    )

    logger.info(f"Unity instance terminated. State: SUCCEEDED")


    def _extract_info(line):
        pattern = r"\[INFO\]\s+(\w+)\.\s+Step:\s+(\d+)\.\s+Time Elapsed:\s+([\d.]+)\s+s\.\s+Mean Reward:\s+([\d.-]+)\.\s+Std of Reward:\s+([\d.-]+)\."
        
        match = re.search(pattern, line)
        
        if match:
            behaviour, step, time_elapsed, mean_reward, std_reward = match.groups()
            
            json_data = {
                "id":0,
                "behaviour": behaviour,
                "Step": int(step),
                "Time Elapsed": float(time_elapsed),
                "Mean Reward": float(mean_reward),
                "Std of Reward": float(std_reward)
            }
            
            return json_data
        return None