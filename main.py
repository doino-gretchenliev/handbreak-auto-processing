#!/usr/bin/env python2
import argparse
import logging
import os
import tempfile
import threading
import time
from os.path import expanduser
from lib.persistent_dictionary import PersistentBlockingDictionary
from lib.event_handlers import MediaFilesEventHandler

from watchdog.observers import Observer

DEFAULT_INCLUDE_PATTERN = ['*.mp4', '*.mpg', '*.mov', '*.mkv', '*.avi']

logging.basicConfig(level=logging.INFO, format='%(asctime)-15s - %(message)s')


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

queue_store_directory = os.path.join(queue_directory, '.handbreak-auto-processing')

processing_dict = PersistentBlockingDictionary(queue_store_directory)


def list_media_files():
    logging.info("Current processing queue:")
    logging.info("Media file path : Processing")
    for media_file_path in processing_dict.iterkeys():
        logging.info("{} : {}".format(media_file_path, processing_dict[media_file_path]))


def process_media_file():
    global current_processing_file_path
    get_media_file()

    if current_processing_file_path is not None:
        try:
            logging.info("Processing file [{}]".format(current_processing_file_path))
            time.sleep(30)
            logging.info("File [{}] processed successfully".format(current_processing_file_path))
            del processing_dict[current_processing_file_path]
            current_processing_file_path = None
        except Exception:
            logging.info(
                "File [{}] returned to processing queue after processing error".format(current_processing_file_path))
            return_current_processing_file_path()


def get_media_file():
    global current_processing_file_path
    try:
        current_processing_file_path = processing_dict.get_by_value_and_update(False, True, True)
    except Exception:
        logging.exception("Can't obtain media file to process")


def return_current_processing_file_path():
    global current_processing_file_path
    if current_processing_file_path is not None:
        processing_dict[current_processing_file_path] = False
        logging.info("File [{}] returned to processing queue".format(current_processing_file_path))
        current_processing_file_path = None


if __name__ == "__main__":
    logging.info("Watching directories: {}".format(watch_directories))
    logging.info("Include patterns: {}".format(include_pattern))
    logging.info("Exclude patterns: {}".format(exclude_pattern))
    logging.info("Case sensitive: [{}]".format(case_sensitive))

    list_media_files()
    event_handler = MediaFilesEventHandler(processing_dict, include_pattern, exclude_pattern, case_sensitive)

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
