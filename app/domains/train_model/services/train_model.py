import asyncio
from functools import partial
import json
import logging
import os
import subprocess
import threading
import re
import uuid

import yaml
import httpx
import traceback

from app.clients.rabbitmq_client import RabbitMQClient, get_rabbitmq_client
from app.clients.redis_client import RedisClient
from app.domains.train_model.schemas.train_job_instance import TrainJobInstance
from app.settings.settings import settings
from app.domains.train_model.schemas.constants import TrainJobInstanceStatus, TrainJobType
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
    
    try:
        run_id = train_job_instance.run_id
        logger.info(f"Preparing to launch Unity instance {run_id}")

        run_path = settings.unity_reults / str(run_id)
        run_path.mkdir(parents=True, exist_ok=True)

        #TODO Save model config yml to be loaded by ML 

        behaviour_name = train_job_instance.nn_model_config.behavior_name
        steps = train_job_instance.nn_model_config.steps

        if train_job_instance.job_type == TrainJobType.RESUME:
              UpdateMaxSteps(steps, behaviour_name, false)

        UpdateMaxSteps(steps, behaviour_name)

        job_count = redis_client.increment_trained_jobs_count()
        behaviour_path = settings.unity_behaviors_dir / f"{behaviour_name}.yml"
        env_pah = settings.unity_envs_dir / "test-env.x86_64"
        port_suffix = str(job_count % 20)
        port = "500" + port_suffix
    
        os.chmod(env_pah, 0o777)

        cmd = (
            f"mlagents-learn {behaviour_path} "
            f"--run-id {str(run_id)} "
            f"--force "
            f"--env {env_pah} " 
            f"--no-graphics "
            f"--base-port {port}"
        )
        rabbitmq_client.enqueue_train_job_status_update(
            train_job_instance.run_id, TrainJobInstanceStatus.STARTING
        )

 
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
        logger.info(f"Unity instance Launched run_id: {run_id}")

        ml_log = []

        while(True):
            retcode = p.poll() 
            line = p.stdout.readline() # type:ignore
            line = line.decode('utf-8')
            ml_log.append(line)
            metrics = _extract_metrics(line)
            if metrics:
                redis_client.push_log_metrics(run_id, metrics)

            if retcode is not None:
                _check_if_succeeded(ml_log[len(line) - 3])
                logger.info(f"Unity instance terminated: {run_id}")
                ml_log.append("exit")
                break

        _send_model_to_endpoint(
            run_id,
            behaviour_name,
            train_job_instance.central_node_url

        )

        rabbitmq_client.enqueue_train_job_status_update(
            train_job_instance.run_id, TrainJobInstanceStatus.SUCCEEDED
        )


        logger.info(f"Unity instance SUCCEEDED {run_id}")

    except Exception as e:
        logger.error(f"Unity instance Failed {run_id}  ERROR: {e}\n{traceback.format_exc()}")
        rabbitmq_client.enqueue_train_job_status_update(
            train_job_instance.run_id, TrainJobInstanceStatus.FAILED
        )
        return
    finally:
        with open(f"{run_path}/metrics.txt", mode="w", buffering=1) as file:
            file.writelines(ml_log)

    
def _send_model_to_endpoint(
        run_id: uuid.UUID,
        behavior_name: str,
        central_node_host: str
    ):

    url = f"http://{central_node_host}/api/v1/train-jobs/{run_id}/nn-models"

    model_path = f"results/{run_id}/{behavior_name}.onnx"

    try:
        with httpx.Client() as client:
            with open(model_path, 'rb') as model_file:
                files = {'nn_model': model_file}
                response = client.put(url, files=files)

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to send model. Status code: {response.status_code}, Response: {response.text}")

    except Exception as e:
        print(f"Error: {e}")

def _check_if_succeeded(line: str):
    logger.info(line)
    if "[INFO] Copied" in line:
        return True
    else:
        raise Exception(line)

def UpdateMaxSteps(steps: int, behavior_name: str, add: bool = False):

    file_path = settings.unity_behaviors_dir / f"{behavior_name}.yml"

    if not file_path.exists():
        return f"Error: File {file_path} does not exist."

    try:
        with open(file_path, 'r') as file:
            data = yaml.safe_load(file)

        if add:
            data['behaviors'][behavior_name]['max_steps'] += steps 
        else:
            data['behaviors'][behavior_name]['max_steps'] = steps

        with open(file_path, 'w') as file:
            yaml.safe_dump(data, file)

        return f"Successfully updated max_steps for {behavior_name}."

    except Exception as e:
        return f"Error updating max_steps: {str(e)}"


def _extract_metrics(line) -> str:
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
        
        return json.dumps(json_data)
    return None