import logging
import os
import select
import signal
import subprocess
import threading


class InvalidOperationException(Exception):
    pass


# noinspection PyClassHasNoInit
class GlobalInterruptableThreadHandler:
    threads = []
    initialized = False

    @staticmethod
    def initialize():
        signal.signal(signal.SIGTERM, GlobalInterruptableThreadHandler.sig_handler)
        GlobalInterruptableThreadHandler.initialized = True

    @staticmethod
    def add_thread(thread):
        if threading.current_thread().name != 'MainThread':
            raise InvalidOperationException("InterruptableThread objects may only be started from the Main thread.")

        if not GlobalInterruptableThreadHandler.initialized:
            GlobalInterruptableThreadHandler.initialize()

        GlobalInterruptableThreadHandler.threads.append(thread)

    @staticmethod
    def sig_handler(signum, frame):
        for thread in GlobalInterruptableThreadHandler.threads:
            thread.interrupted = True
            os.kill(thread.call_process.pid, signal.SIGINT)
            thread.stop()
            thread.join()

        GlobalInterruptableThreadHandler.threads = []


class InterruptableThread:
    def __init__(self, log_file_location, command, timeout, stdout_log_level=logging.INFO,
                 stderr_log_level=logging.ERROR, target=None, **kwargs):
        self.logger = logging.getLogger(log_file_location)

        formatter = logging.Formatter('[%(asctime)-15s] [%(levelname)s]: %(message)s')
        file_handler = logging.FileHandler(filename=log_file_location, encoding='utf-8')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        self.logger.setLevel(logging.INFO)

        self.interrupted = False
        self.exit_code = None
        self.timeout = timeout
        kill = lambda process: process.kill()
        self.call_process = subprocess.Popen("{}".format(command), stdout=subprocess.PIPE,
                                             stderr=subprocess.PIPE, shell=True, **kwargs)
        self.log_levels = {self.call_process.stdout: stdout_log_level, self.call_process.stderr: stderr_log_level}
        self.timer = threading.Timer(timeout, kill, [self.call_process])

        self.stop_requested = threading.Event()
        self.t = threading.Thread(target=target, args=[self]) if target else threading.Thread(target=self.run)

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

    def start(self):
        GlobalInterruptableThreadHandler.add_thread(self)
        self.t.start()

    def stop(self):
        self.stop_requested.set()

    def is_stop_requested(self):
        return self.stop_requested.is_set()

    def join(self):
        try:
            while self.t.is_alive():
                self.t.join(timeout=1)
        except KeyboardInterrupt:
            self.stop_requested.set()
            self.t.join()
