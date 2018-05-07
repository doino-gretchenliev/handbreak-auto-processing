from aenum import Enum
from peewee import CharField


class NodeState(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    SUSPENDED = "suspended"


class NodeStateField(CharField):

    def db_value(self, value):
        return value.value

    def python_value(self, value):
        return NodeState(value)
