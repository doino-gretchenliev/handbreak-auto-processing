import uuid
from datetime import datetime

from humanize import naturaltime, apnumber
from peewee import Proxy, Model, UUIDField, DateTimeField, TextField, IntegerField, CharField

from lib.nodes.node_state import NodeState, NodeStateField

proxy = Proxy()


class BaseModel(Model):
    class Meta:
        database = proxy
        table_name = 'nodes'
        order_by = ['-status']
        indexes = (
            (('id', 'hostname'), True),
        )


class Node(BaseModel):
    id = UUIDField(column_name='id', index=True, unique=True, primary_key=True)
    hostname = CharField(column_name='hostname', index=True)
    status = NodeStateField(column_name='status', index=True)
    date_become_online = DateTimeField(column_name='date_become_online', null=True)
    date_become_offline = DateTimeField(column_name='date_become_offline', null=True)
    cpu_threads = IntegerField(column_name='cpu_threads')
    cpu_details = CharField(column_name='cpu')
    silent_periods = TextField(column_name='silent_periods', null=True)

    def __repr__(self):
        return "<{klass} @{id:x} {attrs}>".format(
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs=" ".join("{}={!r}".format(k, v) for k, v in self.__data__.items()),
        )

    @property
    def identifier(self):
        return "\"{}\" | \"{}\"".format(str(self.id), str(self.file_path))

    def dict(self, humanize=False):
        def to_json(value):
            if isinstance(value, datetime):
                return naturaltime(value) if humanize else value.isoformat()
            elif isinstance(value, uuid.UUID):
                return str(value)
            elif isinstance(value, NodeState):
                return value.value
            elif isinstance(value, int):
                return apnumber(value) if humanize else value
            else:
                return str(value)

        return {k: to_json(v) for k, v in self.__data__.items()}
