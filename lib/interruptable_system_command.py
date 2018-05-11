import logging
import os
import select
import signal
import subprocess
from threading import Thread


class InterruptableSystemCommandThread(Thread):

    def __init__(self, command, env, stdout_log_level=logging.INFO,
                 stderr_log_level=logging.ERROR, **kwargs):
        Thread.__init__(self, **kwargs)

        self.logger = logging.getLogger(__name__)

        self.interrupted = False
        self.exit_code = None

        if env:
            self.logger.debug('\n'.join(['{}={}'.format(k, v) for k, v in env.iteritems()]))
        self.env = env

        self.logger.debug(command)
        self.command = command
        self.stdout_log_level = stdout_log_level
        self.stderr_log_level = stderr_log_level
        self.call_process = None
        self.log_levels = {}
        self.suspended = False

    def run(self):
        self.call_process = subprocess.Popen(self.command, env=self.env, shell=True, stdout=subprocess.PIPE,
                                             stderr=subprocess.PIPE, stdin=subprocess.PIPE, preexec_fn=os.setpgrp)
        self.log_levels = {self.call_process.stdout: self.stdout_log_level,
                           self.call_process.stderr: self.stderr_log_level}

        while self.call_process.poll() is None:
            self.__check_io()

        self.__check_io()
        self.exit_code = self.call_process.wait()

    def kill(self, soft_kill=True):
        if not self.call_process.poll():
            if self.suspended:
                self.resume()
            if soft_kill:
                os.killpg(os.getpgid(self.call_process.pid), signal.SIGINT)
            else:
                os.killpg(os.getpgid(self.call_process.pid), signal.SIGTERM)
            self.interrupted = True

    def suspend(self):
        if not self.suspended:
            os.killpg(os.getpgid(self.call_process.pid), signal.SIGSTOP)
            self.suspended = True
        else:
            raise Exception("process is already suspended")

    def resume(self):
        if self.suspended:
            os.killpg(os.getpgid(self.call_process.pid), signal.SIGCONT)
            self.suspended = False
        else:
            raise Exception("process is already running")

    def __check_io(self):
        ready_to_read = select.select([self.call_process.stdout, self.call_process.stderr], [], [], 1)[0]
        for io in ready_to_read:
            line = io.readline()
            self.logger.log(self.log_levels[io], line[:-1])
