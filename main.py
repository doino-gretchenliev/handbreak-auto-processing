#!/usr/bin/env python2
import argparse
import logging
import sys
import logging.handlers
import os
import tempfile
import threading
import time
import signal
from os.path import expanduser
from lib.system_calls_thread import SystemCallThread

from lib.persistent_dictionary import PersistentAtomicDictionary
from lib.event_handlers import MediaFilesEventHandler

from watchdog.observers import Observer

DEFAULT_INCLUDE_PATTERN = ['*.mp4', '*.mpg', '*.mov', '*.mkv', '*.avi']


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
parser.add_argument('-w', '--watch-directory', help='Directory to watch for new media files', required=True,
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

parser.add_argument('-c', '--handbreak-command', help='Handbreak command to execute', required=True)
parser.add_argument('-t', '--handbreak-timeout', help='Timeout of Handbreak command(hours)\n'
                                                       '(default: 15)', default=15)
parser.add_argument('-f', '--file-extension', help='Output file extension\n'
                                                   '(default: mp4)', default='mp4')
parser.add_argument('-d', '--delete', help='Delete original file', action='store_true')
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

def list_media_files():
    logger.info("Current processing queue:")
    logger.info("[Media file path : Processing]")
    for media_file_path in processing_dict.iterkeys():
        logger.info("[{} : {}]".format(media_file_path, processing_dict[media_file_path]))


def process_media_file():
    global current_processing_file_path
    get_media_file()

    if current_processing_file_path is not None:
        try:
            logger.info("Processing file [{}]".format(current_processing_file_path))
            execute_handbreak_command(current_processing_file_path)
            logger.info("File [{}] processed successfully".format(current_processing_file_path))
            del processing_dict[current_processing_file_path]
            current_processing_file_path = None
        except Exception:
            logger.exception(
                "File [{}] returning to processing queue after processing error".format(current_processing_file_path))
            return_current_processing_file_path()


def execute_handbreak_command(file):
    file_directory = os.path.dirname(file)
    file_name = os.path.splitext(os.path.basename(file))[0]
    transcoded_file = os.path.join(file_directory, "{}_transcoded.{}".format(file_name, file_extension))
    log_file = os.path.join(file_directory, "{}_transcoding.log".format(file_name))

    command = "{handbreak_command} -input {input_file} -output {output_file}"\
        .format(handbreak_command=handbreak_command,
                input_file=file,
                output_file=transcoded_file
                )
    logger.debug(command)

    global system_call_thread
    system_call_thread = SystemCallThread(log_file, "ping 8.8.8.8", handbreak_timeout)
    system_call_thread.start()
    system_call_thread.join()

    if system_call_thread.exit_code == -9:
        raise Exception("Handbreak processes killed after {} hours".format(handbreak_timeout / 60 / 60))
    elif system_call_thread.exit_code != 0:
        raise Exception("Handbreak processes failed. Please, check the transcoding log file [{}]".format(log_file))
    else:
        os.remove(log_file)
        if delete:
            os.remove(file)
    system_call_thread = None


def get_media_file():
    global current_processing_file_path
    try:
        current_processing_file_path = processing_dict.get_by_value_and_update(False, True, True)
    except Exception:
        logger.exception("Can't obtain media file to process")


def return_current_processing_file_path():
    global current_processing_file_path
    if current_processing_file_path is not None:
        processing_dict[current_processing_file_path] = False
        logger.info("File [{}] returned to processing queue".format(current_processing_file_path))
        current_processing_file_path = None


def clean(signal, frame):
    logger.info("Processes interrupted by the user exiting...")
    return_current_processing_file_path()
    observer.stop()
    observer.join()
    global system_call_thread
    if system_call_thread:
        system_call_thread.join()
    exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, clean)
    signal.signal(signal.SIGINT, clean)

    logger.info("Watching directories: {}".format(watch_directories))
    logger.info("Include patterns: {}".format(include_pattern))
    logger.info("Exclude patterns: {}".format(exclude_pattern))
    logger.info("Case sensitive: [{}]".format(case_sensitive))

    if len(processing_dict) > 0:
        list_media_files()
    event_handler = MediaFilesEventHandler(processing_dict, include_pattern, exclude_pattern, case_sensitive)

    for watch_directory in watch_directories:
        observer = Observer()
        observer.schedule(event_handler, watch_directory, recursive=True)
        observer.start()

    while True:
        with lock:
            process = threading.Thread(target=process_media_file(), args=())
            process.start()
            process.join()
        time.sleep(10)
