import uuid
from pydantic import BaseModel

from app.domains.train_model.schemas.constants import TrainJobInstanceStatus, TrainJobType


class NnModelConfig(BaseModel):
    behavior_name: str
    steps: int


class EnvConfig(BaseModel):
    agent_id: str
    env_id: str
    num_of_areas: int

class TrainJobInstance(BaseModel):
    centra_node_id: uuid.UUID
    central_node_url: str
    run_id: uuid.UUID
    job_status: TrainJobInstanceStatus
    job_type: TrainJobType
    nn_model_config: NnModelConfig
    agent_config: str
    env_config: EnvConfig