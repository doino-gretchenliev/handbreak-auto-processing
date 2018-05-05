import uuid
from datetime import datetime

from peewee import Proxy, Model, UUIDField, DateTimeField, TextField, IntegerField

from lib.media_file_state import MediaFileStateField, MediaFileState
from humanize import naturalsize, naturaldelta, intword, naturaltime

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
    transcoded_file_path = TextField(column_name='transcoded_file_path')
    log_file_path = TextField(column_name='log_file_path')
    status = MediaFileStateField(column_name='status')
    file_size = IntegerField(column_name='file_sizes')
    transcoded_file_size = IntegerField(column_name='transcoded_file_size', null=True)
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

    def dict(self, humanize=False):
        def to_json(value):
            if isinstance(value, datetime):
                return naturaltime(value) if humanize else value.isoformat()
            elif isinstance(value, uuid.UUID):
                return str(value)
            elif isinstance(value, MediaFileState):
                return value.value
            elif isinstance(value, int):
                return naturalsize(value) if humanize else value
            else:
                return str(value)

        return {k: to_json(v) for k, v in self.__data__.items()}
