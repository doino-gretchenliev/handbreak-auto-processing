import logging
import os
import time
from threading import Thread
from threading import Timer

from lib.exceptions import HandbreakProcessInterrupted
from lib.interruptable_system_command import InterruptableSystemCommandThread
from lib.media_file_state import MediaFileState


class MediaProcessingThread(Thread):

    def __init__(self,
                 mfq,
                 handbreak_command,
                 handbreak_timeout,
                 output_file_extension,
                 delete_orig_file,
                 **kwargs):
        Thread.__init__(self, **kwargs)

        self.logger = logging.getLogger(__name__)

        self.start_execution_time = None
        self.system_call_thread = None
        self.current_processing_file = None
        self.mfq = mfq
        self.handbreak_command = handbreak_command
        self.handbreak_timeout = handbreak_timeout
        self.output_file_extension = output_file_extension
        self.delete_orig_file = delete_orig_file

    def run(self):
        self.start_execution_time = time.time()
        self.__process_media_file()

    def join(self, timeout=None):
        if self.system_call_thread and self.system_call_thread.isAlive():
            self.system_call_thread.kill()
            self.system_call_thread.join()
        super(MediaProcessingThread, self).join(timeout)
        self.start_execution_time = None

    def suspend_media_processing(self):
        try:
            self.system_call_thread.suspend()
            self.logger.info("Media processing is suspended")
        except Exception:
            self.logger.warn("Media processing is already suspended")

    def resume_media_processing(self):
        try:
            self.system_call_thread.resume()
            self.logger.info("Media processing is resumed")
        except Exception:
            self.logger.warn("Media processing is already running")

    def get_processing_time(self):
        if self.start_execution_time:
            return time.time() - self.start_execution_time
        else:
            raise Exception("process is not running")

    def __process_media_file(self):
        self.__get_media_file()

        if self.current_processing_file is not None:
            try:
                self.logger.info("Processing file [{}]".format(self.current_processing_file.identifier))
                self.logger.debug(self.current_processing_file)
                self.__execute_handbreak_command(self.current_processing_file.file_path)
                self.logger.info("File [{}] processed successfully".format(self.current_processing_file.identifier))
                self.logger.debug(self.current_processing_file)
                self.mfq[self.current_processing_file.id, self.current_processing_file.file_path] = MediaFileState.PROCESSED
                self.current_processing_file = None
            except HandbreakProcessInterrupted:
                self.__return_current_processing_file(MediaFileState.WAITING)
            except Exception:
                self.logger.exception(
                    "File [{}] returning to processing queue after processing error, status [{}]".format(
                        self.current_processing_file.identifier, MediaFileState.FAILED.value))
                self.__return_current_processing_file(MediaFileState.FAILED)

    def __execute_handbreak_command(self, file):
        file_directory = os.path.dirname(file)
        file_name = os.path.splitext(os.path.basename(file))[0]
        transcoded_file = os.path.join(file_directory, "{}_transcoded.{}".format(file_name, self.output_file_extension))
        log_file = os.path.join(file_directory, "{}_transcoding.log".format(file_name))

        handbreak_command_logger = logging.getLogger(InterruptableSystemCommandThread.__module__)
        formatter = logging.Formatter('[%(asctime)-15s] [%(levelname)s]: %(message)s')
        file_handler = logging.FileHandler(filename=log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        handbreak_command_logger.handlers = [file_handler]
        handbreak_command_logger.setLevel(self.logger.level)

        current_env = os.environ.copy()
        current_env["INPUT_FILE"] = file
        current_env["OUTPUT_FILE"] = transcoded_file

        self.logger.debug("Handbreak input file: {}".format(file))
        self.logger.debug("Handbreak output file: {}".format(transcoded_file))

        self.system_call_thread = InterruptableSystemCommandThread(self.handbreak_command,
                                                                   env=current_env,
                                                                   name=InterruptableSystemCommandThread.__module__)

        timer = Timer(self.handbreak_timeout, self.system_call_thread.kill)
        timer.start()

        self.system_call_thread.start()
        self.system_call_thread.join()

        if timer.is_alive():
            timer.cancel()

            if self.system_call_thread.interrupted:
                message = "Handbreak process interrupted softly"
                self.logger.debug(message)
                raise HandbreakProcessInterrupted(message)
            elif self.system_call_thread.exit_code != 0:
                raise Exception(
                    "Handbreak processes failed. Please, check the transcoding log file [{}]".format(log_file))
            else:
                self.logger.debug(
                    "Handbreak process finished successfully, removing the transcoding log file [{}]".format(log_file))
                os.remove(log_file)
                if self.delete_orig_file:
                    self.logger.debug("Removing the source file [{}]".format(file))
                    os.remove(file)
        else:
            raise Exception("Handbreak processes killed after {} hours".format(self.handbreak_timeout / 60 / 60))

    def __get_media_file(self):
        try:
            with self.mfq.obtain_lock():
                self.current_processing_file = self.mfq.peek(MediaFileState.WAITING)
                self.mfq[self.current_processing_file.id, self.current_processing_file.file_path] = MediaFileState.PROCESSING
        except Exception:
            self.logger.warn("Can't obtain media file to process")

    def __return_current_processing_file(self, media_file_state):
        if self.current_processing_file is not None:
            self.mfq[self.current_processing_file.id, self.current_processing_file.file_path] = media_file_state
            self.logger.info(
                "File [{}] returned to processing queue, status [{}]".format(self.current_processing_file.identifier,
                                                                             media_file_state.value))
            self.logger.debug(self.current_processing_file)
