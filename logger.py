import logging
import os
import traceback
from logging.handlers import RotatingFileHandler

from common.helper import Singleton


class Logger(object):
    def __init__(self, log_file_dir="./logs", log_file_name="main_log.log", log_format="%(asctime)s %(levelname)s %(message)s", terminator=None, print_stdout=True):
        log_formatter = logging.Formatter(log_format)
        if not os.path.exists(log_file_dir):
            os.makedirs(log_file_dir)
        my_handler = RotatingFileHandler(log_file_dir + "/" + log_file_name, mode='a', maxBytes=5 * 1024 * 1024, backupCount=2, encoding=None, delay=0)
        if terminator is not None:
            my_handler.terminator = terminator
        my_handler.setFormatter(log_formatter)
        my_handler.setLevel(logging.INFO)

        self._print_stdout = print_stdout
        self.app_log = logging.getLogger(log_file_name)
        self.app_log.setLevel(logging.INFO)

        self.app_log.addHandler(my_handler)

        self._log_map = {20: "Info",
                         30: "Warn",
                         40: "Error"}

    def _log(self, level, msg):
        if self._print_stdout:
            print(self._log_map[level] + ": " + msg)
        self.app_log.log(level=level, msg=msg)

    def warn(self, log_string):
        self._log(level=logging.WARN, msg=log_string)

    def info(self, log_string):
        self._log(level=logging.INFO, msg=log_string)

    def error(self, log_string):
        self._log(level=logging.ERROR, msg=log_string)

    def exception(self, log_string: str, exception: Exception):
        self.error(log_string + " " + self.exception_to_string(exception))

    @staticmethod
    def exception_to_string(exception, with_stack_trace=True):
        exception_string = f"{str(type(exception).__name__)}: {str(exception)}"
        if with_stack_trace:
            trace_string = "\n"
            for line in traceback.TracebackException(type(exception), exception, exception.__traceback__, ).format():
                trace_string += line
            exception_string += trace_string
        return exception_string


class GeneralLogger(Logger, metaclass=Singleton):
    pass


warn = info = error = exception = None
if warn is info is error is None:
    logger = GeneralLogger()
    warn = logger.warn
    info = logger.info
    error = logger.error
    exception = logger.exception
