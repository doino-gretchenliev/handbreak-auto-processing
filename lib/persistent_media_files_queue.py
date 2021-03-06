import datetime
import logging
import os

from lib.connection_manager import ConnectionManager
from lib.media_file import MediaFile
from lib.media_file import proxy
from lib.media_file_state import MediaFileState
from lib import logger

class MediaFilesQueue(object):

    def __init__(self, output_file_extension):
        self.output_file_extension = output_file_extension
        ConnectionManager.initialize_proxy(proxy)
        self.__create_table()

    @ConnectionManager.connection(transaction=True)
    def __create_table(self):
        MediaFile.create_table(True)

    @ConnectionManager.connection
    def __len__(self):
        return MediaFile.select().count()

    @ConnectionManager.connection(transaction=True)
    def __delitem__(self, key):
        if isinstance(key, tuple):
            MediaFile.delete().where(MediaFile.id == key[0]).where(MediaFile.file_path == key[1]).execute()
        else:
            MediaFile.delete().where((MediaFile.id == key) | (MediaFile.file_path == key)).execute()

    @ConnectionManager.connection(transaction=True)
    def __setitem__(self, key, status):
        now = datetime.datetime.now()
        if self.__contains__(key):
            update_fields = {'status': status, 'last_modified': now}

            if status == MediaFileState.PROCESSING:
                update_fields['date_started'] = now
            elif status == MediaFileState.PROCESSED:
                transcoded_file_path = self.__getitem__(key).transcoded_file_path
                try:
                    update_fields['transcoded_file_size'] = os.path.getsize(transcoded_file_path)
                except OSError:
                    logger.warn("Unable to obtain transcoded file size [{}]".format(transcoded_file_path))
                update_fields['date_finished'] = now
            elif status == MediaFileState.FAILED:
                update_fields['date_finished'] = now
            elif status == MediaFileState.WAITING:
                update_fields['date_started'] = None
                update_fields['date_finished'] = None
                update_fields['transcoded_file_size'] = None

            if isinstance(key, tuple):
                MediaFile.update(update_fields).where(
                    (MediaFile.id == key[0]) & (MediaFile.file_path == key[1])).execute()
            else:
                MediaFile.update(update_fields).where(MediaFile.id == key).execute()
        else:
            if isinstance(key, tuple):
                file_directory = os.path.dirname(key[1])
                file_name = os.path.splitext(os.path.basename(key[1]))[0]
                transcoded_file = os.path.join(file_directory,
                                               "{}_transcoded.{}".format(file_name, self.output_file_extension))
                log_file = os.path.join(file_directory, "{}_transcoding.log".format(file_name))

                MediaFile.create(id=key[0],
                                 file_path=key[1],
                                 transcoded_file_path=transcoded_file,
                                 log_file_path=log_file,
                                 status=status,
                                 file_size=os.path.getsize(key[1]),
                                 date_added=now,
                                 last_modified=now)
            else:
                raise Exception('media file doesn\'t exist, you must provide both id and file_path')

    @ConnectionManager.connection
    def __getitem__(self, key):
        if isinstance(key, tuple):
            result = MediaFile.select().where((MediaFile.id == key[0]) & (MediaFile.file_path == key[1])).limit(1)
        else:
            result = MediaFile.select().where((MediaFile.id == key) | (MediaFile.file_path == key)).limit(1)
        return result.first() if result else None

    @ConnectionManager.connection
    def __repr__(self):
        result = []
        for media_file in MediaFile.select().iterator():
            result.append(media_file)
        return "MediaFilesQueue({})".format(result)

    @ConnectionManager.connection
    def serialize(self):
        result = []
        for media_file in MediaFile.select().iterator():
            result.append(media_file.dict())
        return result

    @ConnectionManager.connection
    def __iter__(self):
        return MediaFile.select().iterator()

    @ConnectionManager.connection
    def __contains__(self, item):
        if isinstance(item, tuple):
            result = MediaFile.select().where((MediaFile.id == item[0]) & (MediaFile.file_path == item[1])).exists()
        else:
            result = MediaFile.select().where((MediaFile.id == item) | (MediaFile.file_path == item)).exists()
        return result

    def keys(self):
        result = []
        for media_file in self.__iter__():
            result.append(media_file.id)
        return result

    def values(self):
        result = []
        for media_file in self.__iter__():
            result.append(media_file.status)
        return result

    @ConnectionManager.connection(transaction=True)
    def pop(self, status=None):
        result = self.peek(status)
        self.__delitem__(result.id)
        return result

    @ConnectionManager.connection
    def peek(self, status=None):
        if status:
            result = MediaFile.select().where(MediaFile.status == status).first()
        else:
            result = MediaFile.select().first()
        if not result:
            raise Exception('no media file found')
        return result

    @ConnectionManager.connection(transaction=True)
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

    @ConnectionManager.connection(transaction=True)
    def clear(self, safe=True):
        if safe:
            MediaFile.delete().where(MediaFile.status != MediaFileState.PROCESSING).execute()
        else:
            MediaFile.delete().execute()

    @ConnectionManager.connection
    def list(self, humanize=False):
        return [media_file.dict(humanize) for media_file in MediaFile]
