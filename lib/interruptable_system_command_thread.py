import logging
import os
import select
import signal
import subprocess
import threading
import shlex


class InterruptableSystemCommandThread(threading.Thread):

    def __init__(self, log_file_location, command, stdout_log_level=logging.INFO,
                 stderr_log_level=logging.ERROR, **kwargs):
        self.logger = logging.getLogger(log_file_location)

        formatter = logging.Formatter('[%(asctime)-15s] [%(levelname)s]: %(message)s')
        file_handler = logging.FileHandler(filename=log_file_location, encoding='utf-8')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        self.logger.setLevel(logging.INFO)

        self.interrupted = False
        self.exit_code = None

        self.call_process = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE,
                                             stderr=subprocess.PIPE, stdin=subprocess.PIPE, preexec_fn=os.setpgrp, **kwargs)
        self.log_levels = {self.call_process.stdout: stdout_log_level, self.call_process.stderr: stderr_log_level}
        threading.Thread.__init__(self)

    def run(self):
        while self.call_process.poll() is None:
            self.__check_io()

        self.__check_io()
        self.exit_code = self.call_process.wait()

    def kill(self, soft_kill=True):
        if soft_kill:
            self.call_process.send_signal(signal.SIGINT)
        else:
            self.call_process.send_signal(signal.SIGTERM)
        self.interrupted = True

    def __check_io(self):
        ready_to_read = select.select([self.call_process.stdout, self.call_process.stderr], [], [], 1000)[0]
        for io in ready_to_read:
            line = io.readline()
            self.logger.log(self.log_levels[io], line[:-1])
