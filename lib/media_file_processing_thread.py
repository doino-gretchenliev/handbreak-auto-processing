import logging
import os
import sys
from threading import Thread
from threading import Timer

from lib.exceptions import HandbreakProcessInterrupted
from lib.interruptable_system_command_thread import InterruptableSystemCommandThread
from lib.media_file_states import MediaFileStates


class MediaProcessingThread(Thread):

    def __init__(self,
                 processing_dictionary,
                 handbreak_command,
                 handbreak_timeout,
                 output_file_extension,
                 delete_orig_file,
                 **kwargs):
        Thread.__init__(self, **kwargs)

        self.logger = logging.getLogger(__name__)

        self.system_call_thread = None
        self.current_processing_file_path = None
        self.processing_dictionary = processing_dictionary
        self.handbreak_command = handbreak_command
        self.handbreak_timeout = handbreak_timeout
        self.output_file_extension = output_file_extension
        self.delete_orig_file = delete_orig_file

    def run(self):
        self.__process_media_file()

    def join(self, timeout=None):
        if self.system_call_thread and self.system_call_thread.isAlive():
            self.system_call_thread.kill()
            self.system_call_thread.join()
        super(MediaProcessingThread, self).join(timeout)

    def __process_media_file(self):
        self.__get_media_file()

        if self.current_processing_file_path is not None:
            try:
                self.logger.info("Processing file [{}]".format(self.current_processing_file_path))
                self.__execute_handbreak_command(self.current_processing_file_path)
                self.logger.info("File [{}] processed successfully".format(self.current_processing_file_path))
                self.processing_dictionary[self.current_processing_file_path] = MediaFileStates.PROCESSED
                self.current_processing_file_path = None
            except HandbreakProcessInterrupted:
                self.__return_current_processing_file_path(MediaFileStates.WAITING)
            except Exception:
                self.logger.exception(
                    "File [{}] returning to processing queue after processing error, status [{}]".format(
                        self.current_processing_file_path, MediaFileStates.FAILED.value))
                self.__return_current_processing_file_path(MediaFileStates.FAILED)

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
                self.logger.debug("Handbreak process finished successfully, removing the transcoding log file [{}]".format(log_file))
                os.remove(log_file)
                if self.delete_orig_file:
                    self.logger.debug("Removing the source file [{}]".format(file))
                    os.remove(file)
        else:
            raise Exception("Handbreak processes killed after {} hours".format(self.handbreak_timeout / 60 / 60))

    def __get_media_file(self):
        try:
            self.current_processing_file_path = self.processing_dictionary.get_by_value_and_update(MediaFileStates.WAITING,
                                                                                             MediaFileStates.PROCESSING,
                                                                                             True)
        except Exception:
            self.logger.exception("Can't obtain media file to process")

    def __return_current_processing_file_path(self, media_file_state):
        if self.current_processing_file_path is not None:
            self.processing_dictionary[self.current_processing_file_path] = media_file_state
            self.logger.info("File [{}] returned to processing queue, status [{}]".format(self.current_processing_file_path,
                                                                                     media_file_state.value))