from aenum import Enum
from peewee import CharField


class MediaFileStates(Enum):
    PROCESSING = "processing"
    PROCESSED = "processed"
    WAITING = "waiting"
    FAILED = "failed"


class MediaFileStateField(CharField):

    def db_value(self, value):
        return value.value

    def python_value(self, value):
        return MediaFileStates(value)
