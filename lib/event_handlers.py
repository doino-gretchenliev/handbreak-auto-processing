from watchdog.events import EVENT_TYPE_CREATED
from watchdog.events import FileSystemEventHandler
from pathtools.patterns import match_path
import logging


class MediaFilesEventHandler(FileSystemEventHandler):

    processing_dictionary = None
    include_pattern = None
    exclude_pattern = None
    case_sensitive = None

    def __init__(self, processing_dictionary, include_pattern, exclude_pattern, case_sensitive):
        self.processing_dictionary = processing_dictionary
        self.include_pattern = include_pattern
        self.exclude_pattern = exclude_pattern
        self.case_sensitive = case_sensitive

    def on_any_event(self, event):
        if not event.is_directory \
                and match_path(event.src_path,
                               included_patterns=self.include_pattern,
                               excluded_patterns=self.exclude_pattern,
                               case_sensitive=self.case_sensitive) \
                and event.event_type == EVENT_TYPE_CREATED:
            try:
                if not self.processing_dictionary.check_and_add(event.src_path, False, False):
                    logging.info("File [{}] added to processing queue".format(event.src_path))
            except Exception:
                logging.exception("An error occurred during adding of [{}] to processing queue".format(event.src_path))
