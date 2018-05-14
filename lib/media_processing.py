import logging
import os
import socket
import threading
import time

import dateutil.parser
import schedule
from watchdog.events import EVENT_TYPE_CREATED
from watchdog.events import FileSystemEvent

from lib.media_file_processing import MediaProcessingThread
from lib.media_file_state import MediaFileState
from lib.nodes.node_state import NodeState
from lib.utils import compare_list
from lib.connection_manager import ConnectionManager
from lib import logger

class MediaProcessing(object):
    SCAN_FOR_NEW_MEDIA_FILES_FOR_PROCESSING_TIMEOUT = 10

    def __init__(self, mfq, handbreak_command, handbreak_timeout, nodes, delete):
        self.mfq = mfq

        self.handbreak_command = handbreak_command
        self.handbreak_timeout = handbreak_timeout
        self.delete = delete

        self.system_call_thread = None
        self.exiting = False
        self.lock = threading.Lock()
        self.nodes = nodes
        self.last_silent_periods = None
        self.suspended = False

    def get_queue_files(self):
        result = {}
        for media_file in self.mfq:
            result[media_file.id] = media_file
        return result

    @ConnectionManager.connection(transaction=True)
    def delete_media_file(self, media_file):
        if media_file in self.mfq and self.mfq[media_file].status != MediaFileState.PROCESSING:
            del self.mfq[media_file]
        else:
            raise Exception('can\'t delete {} while it\'s processing'.format(media_file))

    @ConnectionManager.connection(transaction=True)
    def retry_media_files(self, media_file=None):
        if not media_file:
            logger.info("Retrying all media files")
            for media_file in self.mfq:
                self.mfq[media_file.id, media_file.file_path] = MediaFileState.WAITING
        else:
            logger.info("Retrying [{}] media file".format(media_file))
            self.mfq[media_file] = MediaFileState.WAITING

    def start(self):
        while not self.exiting:
            with self.lock:
                self.system_call_thread = MediaProcessingThread(self.mfq,
                                                                self.handbreak_command,
                                                                self.handbreak_timeout,
                                                                self.delete,
                                                                name=MediaProcessingThread.__module__)
                self.system_call_thread.start()
                while self.system_call_thread.isAlive():
                    self.__check_media_processing_state()
                    self.__schedule_silent_periods()
                    time.sleep(10)
                self.system_call_thread = None
            time.sleep(self.SCAN_FOR_NEW_MEDIA_FILES_FOR_PROCESSING_TIMEOUT)

    def stop(self):
        self.exiting = True
        if self.system_call_thread:
            self.system_call_thread.join()

    @ConnectionManager.connection(transaction=True)
    def initial_processing(self, watch_directories, event_handler):
        for watch_directory in watch_directories:
            for root, dir_names, file_names in os.walk(watch_directory):
                for filename in file_names:
                    file_path = os.path.join(root, filename).decode('utf-8')
                    if file_path not in self.mfq or (
                            file_path in self.mfq
                            and self.mfq[file_path].status != MediaFileState.FAILED):
                        file_event = FileSystemEvent(file_path)
                        file_event.is_directory = False
                        file_event.event_type = EVENT_TYPE_CREATED
                        event_handler.on_any_event(file_event)

    def __check_media_processing_state(self):
        if not self.suspended and self.nodes[socket.gethostname()].status == NodeState.SUSPENDED:
            self.__suspend_media_processing()
            self.suspended = True
        elif self.suspended and self.nodes[socket.gethostname()].status == NodeState.ONLINE:
            self.__resume_media_processing()
            self.suspended = False

    def __schedule_silent_periods(self):
        try:
            periods = self.nodes.get_silent_periods(socket.gethostname())
            if not self.last_silent_periods or not compare_list(self.last_silent_periods, periods):
                schedule.clear()
                for period in periods:
                    split_period = period.split('-')
                    starting_time = dateutil.parser.parse(split_period[0])
                    end_time = dateutil.parser.parse(split_period[1])

                    schedule.every().day.at(starting_time.strftime("%H:%M")).do(self.__suspend_media_processing)
                    schedule.every().day.at(end_time.strftime("%H:%M")).do(self.__resume_media_processing)
                self.last_silent_periods = periods
                logger.debug("new silent periods rescheduled {}".format(periods))
            schedule.run_pending()
        except Exception:
            logger.debug('no silent periods configured')

    def __suspend_media_processing(self):
        if self.system_call_thread:
            self.system_call_thread.suspend_media_processing()
        else:
            raise Exception('no running media processing found')

    def __resume_media_processing(self):
        if self.system_call_thread:
            self.system_call_thread.resume_media_processing()
        else:
            raise Exception('no running media processing found')
