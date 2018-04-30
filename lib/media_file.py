from peewee import Proxy, Model, UUIDField, DateTimeField, TextField

from lib.media_file_state import MediaFileStateField

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
    date_added = DateTimeField(column_name='date_added', )
    last_modified = DateTimeField(column_name='last_modified', index=True)
    date_started = DateTimeField(column_name='date_started', null=True)
    date_finished = DateTimeField(column_name='date_finished', null=True)
