import time
from typing import Any, Optional
import uuid

from redis import Redis
import redis
from app.domains.train_model.schemas.train_job_instance import TrainJobInstance


from app.domains.train_model.schemas.train_queue import TrainJobQueue



class RedisClient():
    def __init__(self, redis_client: Redis):
        self.redis_client = redis_client


    def save_run_status(self, run_id: uuid.UUID, status: str):
        key = str(run_id)
        self.redis_client.hset(key, "status", status)


    def save_run_status_and_delivery_tag(self, run_id: uuid.UUID, status: str, delivery_tag: int):
        key = str(run_id)
        self.redis_client.hset(key, "status", status)
        self.redis_client.hset(key, "delivery_tag", delivery_tag)


    def save_current_train_job_instance(self, train_job_instance: TrainJobInstance):
        key = "current_train_job"
        self.redis_client.set(key, train_job_instance.json())

    def get_delivery_tag(self, run_id: uuid.UUID) -> int:
        key = str(run_id)
        delivery_tag = self.redis_client.hget(key, "delivery_tag")
        if delivery_tag is not None:
            return int(delivery_tag)
        else:
            raise ValueError(f"No delivery tag found for run_id: {run_id}")

    def retrieve_current_train_job(self) -> Optional[TrainJobInstance]:
        key = "current_train_job"
        train_job_json = self.redis_client.get(key)
        if train_job_json:
            return TrainJobInstance.parse_raw(train_job_json.decode('utf-8'))
        else:
            return None
        

    def increment_trained_jobs_count(self) -> int:
        key = "trained_jobs_count"
        count = self.redis_client.incr(key)
        return count

    def get_trained_jobs_count(self) -> int:
        key = "trained_jobs_count"
        count = self.redis_client.get(key)
        return int(count) if count else 0


    def update_current_train_job(self, **kwargs):
        key = "current_train_job"
        train_job_instance = self.retrieve_current_train_job()
        if train_job_instance:
            for field, value in kwargs.items():
                setattr(train_job_instance, field, value)
            self.save_current_train_job_instance(train_job_instance)


    def delete_current_train_job(self):
        key = "current_train_job"
        self.redis_client.delete(key)


    def write(self, key: str, value: str):
        self.redis_client.append(key, value)


    def retrieve(self, key: str) -> str:
        value = self.redis_client.get(key)
        return value.decode('utf-8') if value else None


    def save_to_file(self, key: str, file_path: str):
        value = self.redis_client.get(key)
        if value:
            with open(file_path, mode="w", buffering=1) as file:
                file.write(value.decode('utf-8'))


    def get_highest_priority_job(self) -> TrainJobQueue:
        # Pop the job with the lowest score (highest priority and latest timestamp)
        job_data = self.redis_client.zpopmin('jobs', 1)
        
        if not job_data:
            return None
        
        # job_data is a list of tuples [(member, score)], so extract the member
        job_json = job_data[0][0]
        
        # Convert the JSON string back to a TrainJobsBase instance
        return TrainJobQueue.parse_raw(job_json)
    
    def get_all_jobs(self) -> list[TrainJobQueue]:
        # Retrieve all members from the sorted set
        all_jobs_data = self.redis_client.zrange('jobs', 0, -1)
        
        if not all_jobs_data:
            return []
        
        # Convert the list of JSON strings back to a list of TrainJobsBase instances
        return [TrainJobQueue.parse_raw(job_data) for job_data in all_jobs_data]
    

def get_redis_client() -> RedisClient:

    connection = redis.Redis(host='redis')
    return RedisClient(connection)