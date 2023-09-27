import uuid
from pydantic import BaseModel

from app.domains.train_model.schemas.constants import TrainJobInstanceStatus, TrainJobType


class TrainJobInstance(BaseModel):
    centra_node_id: uuid.UUID
    central_node_url: str
    run_id: uuid.UUID
    job_status: TrainJobInstanceStatus
    job_type: TrainJobType
    nn_model_config: str
    agent_config: str
    env_config: str