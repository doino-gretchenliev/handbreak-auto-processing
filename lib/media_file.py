import uuid
from datetime import datetime

from peewee import Proxy, Model, UUIDField, DateTimeField, TextField

from lib.media_file_state import MediaFileStateField, MediaFileState

proxy = Proxy()


class BaseModel(Model):
    class Meta:
        database = proxy
        table_name = 'media_files_queue'
        order_by = ['-last_modified']
        indexes = (
            (('id', 'file_path'), True),
        )


class MediaFile(BaseModel):
    id = UUIDField(column_name='id', index=True, unique=True, primary_key=True)
    file_path = TextField(column_name='file_path', index=True, unique=True)
    status = MediaFileStateField(column_name='status', )
    date_added = DateTimeField(column_name='date_added')
    last_modified = DateTimeField(column_name='last_modified', index=True)
    date_started = DateTimeField(column_name='date_started', null=True)
    date_finished = DateTimeField(column_name='date_finished', null=True)

    def __repr__(self):
        return "<{klass} @{id:x} {attrs}>".format(
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs=" ".join("{}={!r}".format(k, v) for k, v in self.__data__.items()),
            )

    @property
    def identifier(self):
        return "\"{}\" | \"{}\"".format(str(self.id), str(self.file_path))

    @property
    def dict(self):
        def to_json(value):
            if isinstance(value, datetime):
                return value.isoformat()
            elif isinstance(value, uuid.UUID):
                return str(value)
            elif isinstance(value, MediaFileState):
                return value.value
            else:
                return str(value)

        return {k: to_json(v) for k, v in self.__data__.items()}
