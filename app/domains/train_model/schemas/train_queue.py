import uuid
from pydantic import BaseModel

from app.domains.train_model.schemas.constants import TrainJobType
from app.domains.train_model.schemas.train_job_instance import EnvConfig, NnModelConfig


class TrainJobQueue(BaseModel):
    centra_node_id: uuid.UUID
    central_node_url: str
    run_id: uuid.UUID
    job_type: TrainJobType
    nn_model_config: NnModelConfig
    agent_config: str
    env_config: EnvConfig
