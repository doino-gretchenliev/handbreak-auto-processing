import logging
import select
import subprocess
import os
import threading


class SystemCallThread(threading.Thread):

    def __init__(self, log_file_location, command, timeout, stdout_log_level=logging.INFO, stderr_log_level=logging.ERROR, **kwargs):
        self.logger = logging.getLogger(log_file_location)

        formatter = logging.Formatter('[%(asctime)-15s] [%(levelname)s]: %(message)s')
        file_handler = logging.FileHandler(log_file_location)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        self.logger.setLevel(logging.INFO)

        self.exit_code = None
        self.timeout = timeout
        kill = lambda process: process.kill()
        self.call_process = subprocess.Popen("{}".format(command), stdout=subprocess.PIPE,
                                             stderr=subprocess.PIPE, shell=True, **kwargs)
        self.log_levels = {self.call_process.stdout: stdout_log_level, self.call_process.stderr: stderr_log_level}
        self.timer = threading.Timer(timeout, kill, [self.call_process])
        threading.Thread.__init__(self)

    def run(self):
        self.timer.start()
        while self.call_process.poll() is None:
            self._check_io()

        self._check_io()
        self.exit_code = self.call_process.wait()
        if self.timer.is_alive():
            self.timer.cancel()

    def _check_io(self):
        ready_to_read = select.select([self.call_process.stdout, self.call_process.stderr], [], [], 1000)[0]
        for io in ready_to_read:
            line = io.readline()
            self.logger.log(self.log_levels[io], line[:-1])
