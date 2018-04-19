#!/usr/bin/env python2
import argparse
import logging
import logging.handlers
import os
import signal
import sys
import tempfile
import threading
import time
import shlex

from os.path import expanduser
from watchdog.events import EVENT_TYPE_CREATED
from watchdog.events import FileSystemEvent
from watchdog.observers import Observer

from lib.event_handlers import MediaFilesEventHandler
from lib.exceptions import MediaProcessingNonRecoverableError
from lib.media_file_processing_thread import MediaProcessingThread
from lib.media_file_states import MediaFileStates
from lib.persistent_dictionary import PersistentAtomicDictionary

DEFAULT_INCLUDE_PATTERN = ['*.mp4', '*.mpg', '*.mov', '*.mkv', '*.avi']
SCAN_FOR_NEW_MEDIA_FILES_FOR_PROCESSING_TIMEOUT = 10


def is_filesystem_case_sensitive():
    result = True
    tmphandle, tmppath = tempfile.mkstemp()
    if os.path.exists(tmppath.upper()):
        result = False
    return result


def set_log_level_from_verbose(verbose_count):
    if not verbose_count:
        return logging.INFO
    elif verbose_count == 1:
        return logging.DEBUG


parser = argparse.ArgumentParser(description='Watch for new media files and automatically process them with Handbreak')
list_watch_group = parser.add_mutually_exclusive_group(required=True)
list_command_group = parser.add_mutually_exclusive_group(required=True)

list_arg = list_watch_group.add_argument('-l', '--list-processing-queue', help='Lists processing queue and exits',
                                         action='store_true')
parser.add_argument('-n', '--retry-media-file',
                    help="Change media file state from [{}] to [{}]".format(MediaFileStates.FAILED.value,
                                                                            MediaFileStates.WAITING.value))
parser.add_argument('-a', '--retry-all-media-files',
                    help="Change all media file states from [{}] to [{}]".format(MediaFileStates.FAILED.value,
                                                                                 MediaFileStates.WAITING.value),
                    action='store_true')

parser.add_argument('-p', '--initial-processing',
                    help="Find and process all files in listed in watch directories(excludes failed media files)",
                    action='store_true')
parser.add_argument('-r', '--reprocess',
                    help="Whether to reprocess files already in processing queue with state [{}]".format(
                        MediaFileStates.PROCESSED.value), action='store_true')

list_watch_group.add_argument('-w', '--watch-directory', help='Directory to watch for new media files',
                              action='append')
parser.add_argument('-q', '--queue-directory', help='Directory to store processing queue\n'
                                                    '(default: {})'.format(expanduser("~")), default=expanduser("~"))
parser.add_argument('-i', '--include-pattern', help='Include for processing files matching include patterns\n'
                                                    '(default: {})'.format(DEFAULT_INCLUDE_PATTERN), action='append')
parser.add_argument('-e', '--exclude-pattern', help='Exclude for processing files matching include patterns',
                    action='append')
parser.add_argument('-s', '--case-sensitive', help='Whether pattern matching should be case sensitive\n'
                                                   '(default: depends on the filesystem)',
                    default=is_filesystem_case_sensitive(), action='store_true')

parser.add_argument("-v", "--verbose", dest="verbose_count", action="count", default=0,
                    help="Enable verbose log output(increases log verbosity for each occurence)")
parser.add_argument('-m', '--max-log-size', help='Max log size in MB; set to 0 to disable log file rotating\n'
                                                 '(default: 100)', default=0)
parser.add_argument('-k', '--max-log-file-to-keep', help='Max number of log files to keep\n'
                                                         '(default: 5)', default=5)

list_command_group.add_argument('-c', '--handbreak-command', help='Handbreak command to execute')
parser.add_argument('-t', '--handbreak-timeout', help='Timeout of Handbreak command(hours)\n'
                                                      '(default: 15)', default=15)
parser.add_argument('-f', '--file-extension', help='Output file extension\n'
                                                   '(default: mp4)', default='mp4')
parser.add_argument('-d', '--delete', help='Delete original file', action='store_true')

list_command_group._group_actions.append(list_arg)
args = parser.parse_args()

watch_directories = args.watch_directory
queue_directory = args.queue_directory
include_pattern = args.include_pattern if args.include_pattern is not None else DEFAULT_INCLUDE_PATTERN
exclude_pattern = args.exclude_pattern
case_sensitive = args.case_sensitive
max_log_size = args.max_log_size
max_log_file_to_keep = args.max_log_file_to_keep
verbose = set_log_level_from_verbose(args.verbose_count)
handbreak_command = args.handbreak_command
handbreak_timeout = float(args.handbreak_timeout) * 60 * 60
file_extension = args.file_extension
delete = args.delete
list_processing_queue = args.list_processing_queue
retry_media_file = args.retry_media_file
retry_all_media_files = args.retry_all_media_files
initial_processing = args.initial_processing
reprocess = args.reprocess

# Logging setup
formatter = logging.Formatter('[%(asctime)-15s] [%(threadName)s] [%(levelname)s]: %(message)s')

logger = logging.getLogger(__name__)
logger.setLevel(verbose)
syslog_handler = logging.StreamHandler(sys.stdout)
file_handler = logging.handlers.RotatingFileHandler(filename='handbreak-auto-processing.log',
                                                    maxBytes=max_log_size,
                                                    backupCount=max_log_file_to_keep,
                                                    encoding='utf-8')
syslog_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)
logger.addHandler(syslog_handler)
logger.addHandler(file_handler)

lock = threading.Lock()
current_processing_file_path = None

queue_store_directory = os.path.join(queue_directory, '.handbreak-auto-processing')

processing_dict = PersistentAtomicDictionary(queue_store_directory)

system_call_thread = None
observers = []


def list_media_files():
    logger.info("Current processing queue:")
    for media_file_path in processing_dict.iterkeys():
        logger.info("[{} : {}]".format(media_file_path, processing_dict[media_file_path].value))


def clean_handler(signal, frame):
    global observers
    global system_call_thread

    logger.info("Processes interrupted by the user exiting...")
    for observer in observers:
        observer.stop()
        observer.join()
    if system_call_thread:
        system_call_thread.join()
    exit(0)


def retry_media_files():
    if retry_all_media_files:
        logger.info("Retrying all media files")
        processing_dict.get_by_value_and_update(MediaFileStates.FAILED, MediaFileStates.WAITING, False)
    else:
        processing_dict[retry_media_file] = MediaFileStates.WAITING
    list_media_files()


def initial_processing(event_handler):
    for watch_directory in watch_directories:
        for root, dir_names, file_names in os.walk(watch_directory):
            for filename in file_names:
                file_path = os.path.join(root, filename).decode('utf-8')
                if file_path not in processing_dict or (
                        file_path in processing_dict
                        and processing_dict[file_path] != MediaFileStates.FAILED):
                    file_event = FileSystemEvent(file_path)
                    file_event.is_directory = False
                    file_event.event_type = EVENT_TYPE_CREATED
                    event_handler.on_any_event(file_event)


if __name__ == "__main__":
    if list_processing_queue:
        if len(processing_dict) > 0:
            list_media_files()
        exit(0)

    if retry_all_media_files or retry_media_file:
        retry_media_files()

    signal.signal(signal.SIGINT, clean_handler)
    signal.signal(signal.SIGTERM, clean_handler)


    logger.info("Handbreak media processor started pid: [{}]".format(os.getpid()))
    logger.info("Watching directories: {}".format(watch_directories))
    logger.info("Include patterns: {}".format(include_pattern))
    logger.info("Exclude patterns: {}".format(exclude_pattern))
    logger.info("Case sensitive: [{}]".format(case_sensitive))

    if len(processing_dict) > 0:
        list_media_files()

    event_handler = MediaFilesEventHandler(processing_dict, include_pattern, exclude_pattern, case_sensitive, reprocess)

    if initial_processing:
        initial_processing(event_handler)

    global observers
    for watch_directory in watch_directories:
        observer = Observer()
        observer.schedule(event_handler, watch_directory, recursive=True)
        observers.append(observer)
        observer.start()

    global system_call_thread
    while True:
        system_call_thread = MediaProcessingThread(processing_dict,
                                                   handbreak_command,
                                                   handbreak_timeout,
                                                   file_extension,
                                                   delete)
        system_call_thread.start()
        while system_call_thread.isAlive():
            pass
        time.sleep(SCAN_FOR_NEW_MEDIA_FILES_FOR_PROCESSING_TIMEOUT)
