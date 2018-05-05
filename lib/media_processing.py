import logging
import os
import threading
import time

import dateutil
import schedule
from watchdog.events import EVENT_TYPE_CREATED
from watchdog.events import FileSystemEvent

from lib.media_file_processing import MediaProcessingThread
from lib.media_file_state import MediaFileState


class MediaProcessing(object):
    SCAN_FOR_NEW_MEDIA_FILES_FOR_PROCESSING_TIMEOUT = 10

    def __init__(self, mfq, handbreak_command, handbreak_timeout, file_extension, delete, periods=None):
        self.logger = logging.getLogger(__name__)
        media_processing_thread_logger = logging.getLogger(MediaProcessingThread.__module__)
        media_processing_thread_logger.handlers = self.logger.handlers
        media_processing_thread_logger.level = self.logger.level

        self.mfq = mfq

        self.handbreak_command = handbreak_command
        self.handbreak_timeout = handbreak_timeout
        self.file_extension = file_extension
        self.delete = delete

        self.system_call_thread = None
        self.exiting = False
        self.lock = threading.Lock()
        if periods:
            self.schedule_silent_periods(periods)

    def get_queue_files(self):
        result = {}
        for media_file in self.mfq:
            result[media_file.id] = media_file
        return result

    def delete_media_file(self, media_file):
        with self.mfq.obtain_lock():
            if media_file in self.mfq and self.mfq[media_file].status != MediaFileState.PROCESSING:
                del self.mfq[media_file]
            else:
                raise Exception('can\'t delete {} while it\'s processing'.format(media_file))

    def retry_media_files(self, media_file=None):
        if not media_file:
            self.logger.info("Retrying all media files")
            with self.mfq.obtain_lock():
                for media_file in self.mfq:
                    self.mfq[media_file.id, media_file.file_path] = MediaFileState.WAITING
        else:
            self.logger.info("Retrying [{}] media files".format(media_file))
            self.mfq[media_file] = MediaFileState.WAITING

    def start(self):
        while not self.exiting:
            with self.lock:
                self.system_call_thread = MediaProcessingThread(self.mfq,
                                                                self.handbreak_command,
                                                                self.handbreak_timeout,
                                                                self.file_extension,
                                                                self.delete,
                                                                name=MediaProcessingThread.__module__)
                self.system_call_thread.start()
                while self.system_call_thread.isAlive():
                    schedule.run_pending()
                    time.sleep(10)
                self.system_call_thread = None
            time.sleep(self.SCAN_FOR_NEW_MEDIA_FILES_FOR_PROCESSING_TIMEOUT)

    def stop(self):
        self.exiting = True
        if self.system_call_thread:
            self.system_call_thread.join()

    def initial_processing(self, watch_directories, event_handler):
        for watch_directory in watch_directories:
            for root, dir_names, file_names in os.walk(watch_directory):
                for filename in file_names:
                    file_path = os.path.join(root, filename).decode('utf-8')
                    with self.mfq.obtain_lock():
                        if file_path not in self.mfq or (
                                file_path in self.mfq
                                and self.mfq[file_path].status != MediaFileState.FAILED):
                            file_event = FileSystemEvent(file_path)
                            file_event.is_directory = False
                            file_event.event_type = EVENT_TYPE_CREATED
                            event_handler.on_any_event(file_event)

    def schedule_silent_periods(self, periods):
        for period in periods:
            splitted_period = period.split('-')
            starting_time = dateutil.parser.parse(splitted_period[0])
            end_time = dateutil.parser.parse(splitted_period[1])

            schedule.every().day.at(starting_time.strftime("%H:%M")).do(self.suspend_media_processing)
            schedule.every().day.at(end_time.strftime("%H:%M")).do(self.resume_media_processing)

    def suspend_media_processing(self):
        if self.system_call_thread:
            self.system_call_thread.suspend_media_processing()
        else:
            raise Exception('no running media processing found')

    def resume_media_processing(self):
        if self.system_call_thread:
            self.system_call_thread.resume_media_processing()
        else:
            raise Exception('no running media processing found')
