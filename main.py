#!/usr/bin/env python2
import argparse
import logging
import os
import pickle
import sqlite3
import tempfile
import threading
import time
import time as _time

from filelock import SoftFileLock
from os.path import expanduser
from pathtools.patterns import match_path
from persistqueue import UniqueQ
from watchdog.events import EVENT_TYPE_CREATED
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

DEFAULT_INCLUDE_PATTERN = ['*.mp4', '*.mpg', '*.mov', '*.mkv', '*.avi']

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)-15s - %(message)s')


def is_filesystem_case_sensitive():
    result = True
    tmphandle, tmppath = tempfile.mkstemp()
    if os.path.exists(tmppath.upper()):
        result = False
    return result


parser = argparse.ArgumentParser(description='Watch for new media files and automatically process them with Handbreak')
parser.add_argument('-w', '--watch-directory', help='Directory to watch for new media files', required=True,
                    action='append')
parser.add_argument('-q', '--queue-directory', help='Directory to store processing queue\n'
                                                    '(default: {})'.format(expanduser("~")), default=expanduser("~"))
parser.add_argument('-i', '--include-pattern', help='Include for processing files matching include patterns\n'
                                                    '(default: {})'.format(DEFAULT_INCLUDE_PATTERN), action='append')
parser.add_argument('-e', '--exclude-pattern', help='Exclude for processing files matching include patterns',
                    action='append')
parser.add_argument('-c', '--case-sensitive', help='Whether pattern matching should be case sensitive\n'
                                                   '(default: depends on the filesystem)',
                    default=is_filesystem_case_sensitive(), action='store_true')

args = parser.parse_args()
watch_directories = args.watch_directory
queue_directory = args.queue_directory
include_pattern = args.include_pattern if args.include_pattern is not None else DEFAULT_INCLUDE_PATTERN
exclude_pattern = args.exclude_pattern
case_sensitive = args.case_sensitive

lock = threading.Lock()
current_processing_file_path = None


class UniqueQueue(UniqueQ):
    def put(self, item):
        updated = False
        obj = pickle.dumps(item)
        try:
            self._insert_into(obj, _time.time())
            updated = True
        except sqlite3.IntegrityError:
            pass
        else:
            self.total += 1
            self.put_event.set()
        return updated


queue_store_directory = os.path.join(queue_directory, '.handbreak-auto-processing')
queue_store_lock_file = os.path.join(queue_store_directory, "data.lock")
queue = UniqueQueue(queue_store_directory, auto_commit=True, multithreading=True)


class MediaFilesEventHandler(FileSystemEventHandler):
    def on_any_event(self, event):
        if not event.is_directory \
                and match_path(event.src_path,
                               included_patterns=include_pattern,
                               excluded_patterns=exclude_pattern,
                               case_sensitive=case_sensitive) \
                and event.event_type == EVENT_TYPE_CREATED:
            try:
                lock = SoftFileLock(queue_store_lock_file)
                with lock:
                    if queue.put(event.src_path):
                        logging.info("File [{}] added to processing queue".format(event.src_path))
            except Exception:
                logging.exception("An error occurred during adding of [{}] to processing queue".format(event.src_path))


def process_media_file():
    global current_processing_file_path
    try:
        lock = SoftFileLock(queue_store_lock_file)
        with lock:
            if queue.size > 0:
                current_processing_file_path = queue.get()
    except Exception:
        logging.exception("Can't obtain media file to process")

    if current_processing_file_path is not None:
        try:
            logging.info("Processing file [{}]".format(current_processing_file_path))
            time.sleep(30)
            logging.info("File [{}] processed successfully".format(current_processing_file_path))
            current_processing_file_path = None
        except Exception:
            logging.info(
                "File [{}] returned to processing queue after processing error".format(current_processing_file_path))
            return_current_processing_file_path()


def return_current_processing_file_path():
    global current_processing_file_path
    if current_processing_file_path is not None:
        lock = SoftFileLock(queue_store_lock_file)
        with lock:
            if queue.put(current_processing_file_path):
                logging.info("File [{}] returned to processing queue".format(current_processing_file_path))
        current_processing_file_path = None


if __name__ == "__main__":
    event_handler = MediaFilesEventHandler()

    for watch_directory in watch_directories:
        observer = Observer()

        observer.schedule(event_handler, watch_directory, recursive=True)
        observer.start()
    try:
        while True:
            with lock:
                process = threading.Thread(target=process_media_file(), args=())
                process.start()
                process.join()
            time.sleep(10)
    except KeyboardInterrupt:
        observer.stop()
        return_current_processing_file_path()
    observer.join()
