from aenum import Enum


class MediaFileStates(Enum):
    PROCESSING = "processing"
    PROCESSED = "processed"
    WAITING = "waiting"
    FAILED = "failed"


