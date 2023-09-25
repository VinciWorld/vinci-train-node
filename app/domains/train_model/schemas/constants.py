import enum


class TrainJobInstanceStatus(str, enum.Enum):
    SUBMITTED = "SUBMITTED"
    RETRIEVED = "RETRIEVED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"

class TrainJobType(str, enum.Enum):
    CREATE = "CREATE"
    RESUME = "RESUME"

instance_in_process = {
    TrainJobInstanceStatus.SUBMITTED,
    TrainJobInstanceStatus.STARTING,
   }
