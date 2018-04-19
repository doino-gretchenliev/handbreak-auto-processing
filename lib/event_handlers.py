import logging
import sys

from pathtools.patterns import match_path
from watchdog.events import EVENT_TYPE_CREATED
from watchdog.events import FileSystemEventHandler

from lib.media_file_states import MediaFileStates

logger = logging.getLogger(__name__)

formatter = logging.Formatter('[%(asctime)-15s] [%(threadName)s] [%(levelname)s]: %(message)s')
syslog_handler = logging.StreamHandler(sys.stdout)
syslog_handler.setFormatter(formatter)
logger.addHandler(syslog_handler)
logger.setLevel(logging.INFO)


class MediaFilesEventHandler(FileSystemEventHandler):
    processing_dictionary = None
    include_pattern = None
    exclude_pattern = None
    case_sensitive = None

    def __init__(self, processing_dictionary, include_pattern, exclude_pattern, case_sensitive, reprocess):
        self.processing_dictionary = processing_dictionary
        self.include_pattern = include_pattern
        self.exclude_pattern = exclude_pattern
        self.case_sensitive = case_sensitive
        self.reprocess = reprocess

    def on_any_event(self, event):
        if not event.is_directory \
                and match_path(event.src_path,
                               included_patterns=self.include_pattern,
                               excluded_patterns=self.exclude_pattern,
                               case_sensitive=self.case_sensitive) \
                and event.event_type == EVENT_TYPE_CREATED:
            try:
                file_path = event.src_path.decode('utf-8')
                if not self.processing_dictionary.check_and_add(file_path,
                                                                MediaFileStates.WAITING,
                                                                self.reprocess):
                    logger.info("File [{}] added to processing queue".format(file_path))
            except Exception:
                logger.exception("An error occurred during adding of [{}] to processing queue".format(file_path))
