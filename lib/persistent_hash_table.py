import datetime
import logging
import os

from playhouse.apsw_ext import SqliteDatabase

from lib.media_file import MediaFile
from lib.media_file import proxy
from lib.media_file_states import MediaFileStates

logger = logging.getLogger(__name__)


def transaction(func):
    def _execute(obj, *args, **kwargs):
        with obj.database.atomic('EXCLUSIVE'):
            return func(obj, *args, **kwargs)

    return _execute


class MediaFilesQueue(object):

    def __init__(self, path):
        self.database = SqliteDatabase(os.path.join(path, 'media-files-queue.db'))
        proxy.initialize(self.database)
        proxy.connect()
        MediaFile.create_table(True)

    def __len__(self):
        return MediaFile.select().count()

    @transaction
    def __delitem__(self, key):
        if isinstance(key, tuple):
            MediaFile.delete().where(MediaFile.id == key[0]).where(MediaFile.file_path == key[1]).execute()
        else:
            MediaFile.delete().where((MediaFile.id == key) | (MediaFile.file_path == key)).execute()

    @transaction
    def __setitem__(self, key, status):
        if isinstance(key, tuple):
            now = datetime.datetime.now()
            if self.__contains__(key):
                update_fields = { 'status' :status, 'last_modified': now }

                if status == MediaFileStates.PROCESSING:
                    update_fields['date_started'] = now
                elif status == MediaFileStates.FAILED or status == MediaFileStates.PROCESSED:
                    update_fields['date_finished'] = now
                elif status == MediaFileStates.WAITING:
                    update_fields['date_started'] = None
                    update_fields['date_finished'] = None

                MediaFile.update(update_fields).where((MediaFile.id == key[0]) & (MediaFile.file_path == key[1])).execute()
            else:
                MediaFile.create(id=key[0], file_path=key[1], status=status, date_added=now, last_modified=now)
        else:
            raise ValueError('you must provide both id and file_path')

    def __getitem__(self, key):
        if isinstance(key, tuple):
            result = MediaFile.select().where((MediaFile.id == key[0]) & (MediaFile.file_path == key[1])).limit(1)
        else:
            result = MediaFile.select().where((MediaFile.id == key) | (MediaFile.file_path == key)).limit(1)
        return result.first() if result else None

    def __repr__(self):
        result = []
        for media_file in MediaFile.select().iterator():
            result.append(media_file)
        return "MediaFilesQueue({})".format(result)

    def __iter__(self):
        return MediaFile.select().iterator()

    def __contains__(self, item):
        if isinstance(item, tuple):
            result = MediaFile.select().where((MediaFile.id == item[0]) & (MediaFile.file_path == item[1])).exists()
        else:
            result = MediaFile.select().where((MediaFile.id == item) | (MediaFile.file_path == item)).exists()
        return result

    def keys(self):
        result = []
        for media_file in self.__iter__():
            result.append((media_file.id, media_file.file_path))
        return result

    def values(self):
        result = []
        for media_file in self.__iter__():
            result.append(media_file.status)
        return result

    @transaction
    def pop(self, status=None):
        if status:
            result = MediaFile.select().where(MediaFile.status == status).first()
        else:
            result = MediaFile.select().first()
        if not result:
            raise Exception('no media file found')
        self.__delitem__(result.id)
        return result

    @transaction
    def touch(self, key):
        if self.__contains__(key):
            now = datetime.datetime.now()
            if isinstance(key, tuple):
                MediaFile.update(last_modified=now) \
                    .where((MediaFile.id == key[0]) & (MediaFile.file_path == key[1])).execute()
            else:
                MediaFile.update(last_modified=now) \
                    .where((MediaFile.id == key) | (MediaFile.file_path == key)).execute()
        else:
            raise Exception('no media file found')

    @transaction
    def clear(self):
        return MediaFile.delete().execute()