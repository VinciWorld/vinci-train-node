from pydantic import BaseModel

from app.domains.train_model.schemas.train_queue import TrainJobQueue


class StreamMessage(BaseModel):
    msg_id: str

class TrainJobStream(StreamMessage):
    train_job: TrainJobQueue