#!/usr/bin/env python2
import argparse
import logging.handlers
import os
import signal
import socket
import sys
import tempfile
from os.path import expanduser
from uuid import uuid4

from watchdog.observers import Observer
from peewee import SqliteDatabase

from lib.utils import configure_logging
from lib.event_handlers import MediaFilesEventHandler
from lib.media_file_state import MediaFileState
from lib.media_processing import MediaProcessing
from lib.nodes.node_state import NodeState
from lib.nodes.nodes_inventory import NodeInventory
from lib.persistent_media_files_queue import MediaFilesQueue
from lib.rest_api import RestApi
from lib.connection_manager import ConnectionManager

DEFAULT_INCLUDE_PATTERN = ['*.mp4', '*.mpg', '*.mov', '*.mkv', '*.avi']
SCAN_FOR_NEW_MEDIA_FILES_FOR_PROCESSING_TIMEOUT = 10


def is_filesystem_case_sensitive():
    result = True
    tmphandle, tmppath = tempfile.mkstemp()
    if os.path.exists(tmppath.upper()):
        result = False
    return result


parser = argparse.ArgumentParser(description='Watch for new media files and automatically process them with Handbreak')
list_watch_group = parser.add_mutually_exclusive_group(required=True)
list_command_group = parser.add_mutually_exclusive_group(required=True)

list_arg = list_watch_group.add_argument('-l', '--list-processing-queue', help='Lists processing queue and exits',
                                         action='store_true')
parser.add_argument('-n', '--retry-media-file',
                    help="Change media file state from [{}] to [{}]".format(MediaFileState.FAILED.value,
                                                                            MediaFileState.WAITING.value))
parser.add_argument('-a', '--retry-all-media-files',
                    help="Change all media file states from [{}] to [{}]".format(MediaFileState.FAILED.value,
                                                                                 MediaFileState.WAITING.value),
                    action='store_true')

parser.add_argument('-p', '--initial-processing',
                    help="Find and process all files in listed in watch directories(excludes failed media files)",
                    action='store_true')
parser.add_argument('-r', '--reprocess',
                    help="Whether to reprocess files already in processing queue with state [{}]".format(
                        MediaFileState.PROCESSED.value), action='store_true')

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

parser.add_argument('-z', '--silent-period',
                    help='A silent period(the media processing command will be suspended) defined as so: [18:45:20:45]. '
                         'You can provide multiple periods', action='append')
parser.add_argument("-x", "--rest-api", action="store_true", default=False, help="Enable REST API on port 6767")

parser.add_argument("-v", "--verbose", action='count', help="Enable verbose log output")
parser.add_argument('-m', '--max-log-size', help='Max log size in MB; set to 0 to disable log file rotating\n'
                                                 '(default: 100)', default=100)
parser.add_argument('-k', '--max-log-file-to-keep', help='Max number of log files to keep\n'
                                                         '(default: 0)', default=0)

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

logging_level = logging.INFO
external_libs_logging_level = logging_level
if args.verbose > 0:
    logging_level = logging.DEBUG
if args.verbose > 1:
    external_libs_logging_level = logging_level

handbreak_command = args.handbreak_command
handbreak_timeout = float(args.handbreak_timeout) * 60 * 60
file_extension = args.file_extension
delete = args.delete
list_processing_queue = args.list_processing_queue
retry_media_file = args.retry_media_file
retry_all_media_files = args.retry_all_media_files
initial_processing = args.initial_processing
reprocess = args.reprocess
silent_period = args.silent_period
enable_rest_api = args.rest_api

logger = logging.getLogger(__name__)
configure_logging('handbreak-auto-processing.log', max_log_size, max_log_file_to_keep, logging_level,
                  external_libs_logging_level)

data_store_directory = os.path.join(queue_directory, '.handbreak-auto-processing')
if not os.path.exists(data_store_directory):
    os.mkdir(data_store_directory)

database_file = os.path.join(data_store_directory, 'data.db')
database = SqliteDatabase(database_file)
ConnectionManager.register_database(database)

mfq = MediaFilesQueue(file_extension)
nodes = NodeInventory()

rest_api = None
observers_list = []


def clean_handler(signal, frame):
    logger.info("Processes interrupted by the user exiting [{}], please wait while cleaning up...".format(signal))
    if rest_api:
        rest_api.stop()
    if media_processing:
        media_processing.stop()
    for observer in observers_list:
        observer.stop()
        observer.join()
    toggle_node_state()
    exit(0)


def toggle_node_state():
    if socket.gethostname() in nodes:
        current_state = nodes[socket.gethostname()].status
        if current_state == NodeState.OFFLINE:
            nodes[socket.gethostname()] = NodeState.ONLINE
        else:
            nodes[socket.gethostname()] = NodeState.OFFLINE
    else:
        nodes[uuid4(), socket.gethostname()] = NodeState.ONLINE


if __name__ == "__main__":
    toggle_node_state()
    if silent_period:
        nodes.set_silent_periods(socket.gethostname(), silent_period)

    media_processing = MediaProcessing(
        mfq,
        handbreak_command,
        handbreak_timeout,
        nodes,
        delete
    )

    if enable_rest_api:
        rest_api = RestApi(media_processing, nodes)

    if list_processing_queue:
        if len(mfq) > 0:
            logger.info("Current processing queue:")
            media_files = media_processing.get_queue_files()
            for media_file, status in media_files.items():
                logger.info("[{} : {}]".format(media_file, status.value))
        else:
            logger.info("Processing queue is empty")
        exit(0)

    if retry_all_media_files:
        media_processing.retry_media_files()

    if retry_media_file:
        media_processing.retry_media_files(retry_media_file)

    signal.signal(signal.SIGINT, clean_handler)
    signal.signal(signal.SIGTERM, clean_handler)

    logger.info("Handbreak media processor started pid: [{}]".format(os.getpid()))
    logger.info("Watching directories: {}".format(watch_directories))
    logger.info("Include patterns: {}".format(include_pattern))
    logger.info("Exclude patterns: {}".format(exclude_pattern))
    logger.info("Case sensitive: [{}]".format(case_sensitive))
    logger.info("Processing queue size: [{}]".format(len(mfq)))

    # watch for media files
    event_handler = MediaFilesEventHandler(mfq, include_pattern, exclude_pattern, case_sensitive, reprocess)

    if initial_processing:
        media_processing.initial_processing(watch_directories, event_handler)

    for watch_directory in watch_directories:
        observer = Observer()
        observer.schedule(event_handler, watch_directory, recursive=True)
        observer.setDaemon(True)
        observer.start()
        observers_list.append(observer)

    # start media files processing
    media_processing.start()
