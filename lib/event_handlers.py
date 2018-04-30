import logging
from uuid import uuid4

from pathtools.patterns import match_path
from watchdog.events import EVENT_TYPE_CREATED
from watchdog.events import FileSystemEventHandler

from lib.media_file_state import MediaFileState

logger = logging.getLogger(__name__)


class MediaFilesEventHandler(FileSystemEventHandler):
    mfq = None
    include_pattern = None
    exclude_pattern = None
    case_sensitive = None

    def __init__(self, mfq, include_pattern, exclude_pattern, case_sensitive, reprocess):
        self.mfq = mfq
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
                with self.mfq.database.atomic('EXCLUSIVE'):
                    if file_path not in self.mfq or self.reprocess:
                        id = uuid4()
                        self.mfq[id, file_path] = MediaFileState.WAITING
                        media_file = self.mfq[id, file_path]
                        logger.info("File [{}] added to processing queue".format(media_file.identifier))
                        logger.debug(media_file)
            except Exception:
                logger.exception("An error occurred during adding of [{}] to processing queue".format(file_path))
