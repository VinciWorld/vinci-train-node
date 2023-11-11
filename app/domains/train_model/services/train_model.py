import asyncio
from functools import partial
from io import BytesIO
import json
import logging
import os
from pathlib import Path
import subprocess
import threading
import re
import uuid
import zipfile

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


"""
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
"""


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
        args=(train_job_instance, redis_client, rabbitmq_client, method.delivery_tag)
    ).start()

def _launch_unity_instante(
        train_job_instance: TrainJobInstance,
        redis_client: RedisClient,
        rabbitmq_client: RabbitMQClient,
        delivery_tag
        ):
    
    try:
        rabbitmq_client.running_jobs_count += 1
        ml_log = []
        train_metrics = []
        run_id = train_job_instance.run_id
        logger.info(f"Preparing to launch Unity instance {train_job_instance}")

        run_path = settings.unity_reults / str(run_id)
        run_path.mkdir(parents=True, exist_ok=True)

        #TODO Save model config yml to be loaded by ML 

        behaviour_name = train_job_instance.nn_model_config.behavior_name
        steps = train_job_instance.nn_model_config.steps


        model_checkpoint_id = None
        if train_job_instance.job_type == TrainJobType.RESUME:
            UpdateMaxSteps(steps, behaviour_name, True)
            _retrieve_and_save_model_checkpoint(run_id, behaviour_name, train_job_instance.central_node_url)
            model_checkpoint_id = str(run_id)

        else:
            UpdateMaxSteps(steps, behaviour_name)


        behaviour_path = settings.unity_behaviors_dir / f"{behaviour_name}.yml"
        env_pah = settings.unity_envs_dir / train_job_instance.env_config.env_id / "env.x86_64"

        # Configure instance port
        job_count = redis_client.increment_trained_jobs_count()
        port_suffix = str(job_count % 20)
        port = "500" + port_suffix

        os.chmod(env_pah, 0o777)

        cmd = (
            f"mlagents-learn {behaviour_path} "
            f"--run-id {str(run_id)} "
            f"--force "
            f"--env {env_pah} " 
            f"--no-graphics "
            f"--base-port {port} "
            f"--torch-device cpu "
        )

        if model_checkpoint_id is not None:
            cmd = cmd.replace("--force", "--resume")
            cmd += f"--initialize-from={model_checkpoint_id}"

        rabbitmq_client.enqueue_train_job_status_update(
            train_job_instance.run_id, TrainJobInstanceStatus.STARTING
        )

 
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
        logger.info(f"Unity instance Launched run_id: {run_id}")

        while(True):
            retcode = p.poll() 
            line = p.stdout.readline() # type:ignore
            line = line.decode('utf-8')
            ml_log.append(line)
            metrics = _extract_metrics(line)
            
            if metrics:
                train_metrics.append(metrics)
                redis_client.push_log_metrics(run_id, metrics)

            if retcode is not None:
                _check_if_succeeded(ml_log[len(line) - 3])
                logger.info(f"Unity instance terminated: {run_id}")
                ml_log.append("exit")
                break

        #_send_model_to_endpoint(
        #    run_id,
        #    behaviour_name,
        #    train_job_instance.central_node_url
        #)

        _send_train_results(
            run_id,
            behaviour_name,
            train_job_instance.central_node_url,
            train_metrics
        )

        rabbitmq_client.enqueue_train_job_status_update(
            train_job_instance.run_id, TrainJobInstanceStatus.SUCCEEDED
        )

        rabbitmq_client.acknowledge_job_sucess(delivery_tag)


        logger.info(f"Unity instance SUCCEEDED {run_id}")

    except Exception as e:
        logger.error(f"Unity instance Failed {run_id}  ERROR: {e}\n{traceback.format_exc()}")
        rabbitmq_client.enqueue_train_job_status_update(
            train_job_instance.run_id, TrainJobInstanceStatus.FAILED
        )
        UpdateMaxSteps(-steps, behaviour_name, True)

        rabbitmq_client.acknowledge_job_failed_and_requeue(delivery_tag)
        ml_log.append(str(e))
        return
    finally:
        with open(f"{run_path}/ml_log.txt", mode="w", buffering=1) as file:
            file.writelines(ml_log)
        
        rabbitmq_client.running_jobs_count -= 1


def _retrieve_and_save_model_checkpoint(
        run_id: uuid.UUID,
        behavior_name: str,
        central_node_host: str
):
    url = f"{settings.http_prefix}://{central_node_host}/api/v1/train-jobs/{run_id}/checkpoint"

    try:
        with httpx.Client() as client:
            response = client.get(url)

            logger.info("checkpoint Status: {response.status_code}")
            if response.status_code == 200:
                checkpoint_dir = Path("results") / str(run_id) / behavior_name
                checkpoint_dir.mkdir(parents=True, exist_ok=True)
                checkpoint_path = checkpoint_dir / "checkpoint.pt"
                logger.info(f"Save checkpoint run id: {str(run_id)} at {checkpoint_path}")
                with open(checkpoint_path, mode="wb") as file:
                    file.write(response.content)
            else:
                raise Exception(f"Failed to retrieve model checkpoint. Status code: {response.status_code}")
    except Exception as e:
        raise e

    
def _send_model_checkpooint_and_metrics(
        run_id: uuid.UUID,
        behavior_name: str,
        central_node_host: str
    ):

    url = f"{settings.http_prefix}://{central_node_host}/api/v1/train-jobs/{run_id}/nn-model"
    #url = f"https://{central_node_host}/api/v1/train-jobs/{run_id}/nn-model"

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

def _send_model_to_endpoint(
        run_id: uuid.UUID,
        behavior_name: str,
        central_node_host: str
    ):

    url = f"{settings.http_prefix}://{central_node_host}/api/v1/train-jobs/{run_id}/nn-model"
    #url = f"https://{central_node_host}/api/v1/train-jobs/{run_id}/nn-model"

    model_path = f"results/{run_id}/{behavior_name}.onnx"

    try:
        with httpx.Client() as client:
            with open(model_path, 'rb') as model_file:
                files = {'nn_model': model_file}
                response = client.post(url, files=files)

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to send model. Status code: {response.status_code}, Response: {response.text}")

    except Exception as e:
        print(f"Error: {e}")


def _send_train_results(
        run_id: uuid.UUID,
        behavior_name: str,
        central_node_host: str,
        metrics: list
    ):

    url = f"{settings.http_prefix}://{central_node_host}/api/v1/train-jobs/{run_id}/results"
    directory_to_zip = f"results/{run_id}/"

    files_to_include = {
        ".": ["configuration.yaml", "metrics.txt", f"{behavior_name}.onnx"],
        behavior_name: ["checkpoint.pt"],
        "run_logs": ["Player-0.log", "timers.json", "training_status.json"]
    }

    file_renames = {
        f"{behavior_name}.onnx": "model.onnx",
        "Player-0.log": "unity.log"
    }

    zip_buffer = BytesIO()

    with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED) as zf:
        for dirpath, subdirs, files in os.walk(directory_to_zip):
            for filename in files:
                if dirpath.endswith(behavior_name) and filename.startswith("events.out.tfevents."):
                    file_path = os.path.join(dirpath, filename)
                    zf.write(file_path, filename)
                    continue

                relative_dirpath = os.path.relpath(dirpath, directory_to_zip)
                if relative_dirpath in files_to_include and filename in files_to_include[relative_dirpath]:
                    file_path = os.path.join(dirpath, filename)
                    arcname = file_renames.get(filename, filename)
                    zf.write(file_path, arcname)
        
        json_content = json.dumps(metrics, indent=4)
        zf.writestr('metrics_data.json', json_content)

    zip_buffer.seek(0)

    try:
        with httpx.Client() as client:
            files = {'results_zip': ('results.zip', zip_buffer)}
            response = client.post(url, files=files)

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to send model. Status code: {response.status_code}, Response: {response.text}")

    except Exception as e:
        raise e


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
            "step": int(step),
            "time_elapsed": float(time_elapsed),
            "mean_reward": float(mean_reward),
            "std_reward": float(std_reward)
        }
        
        return json.dumps(json_data)
    return None