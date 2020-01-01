import logging
from logging.handlers import RotatingFileHandler


class Singleton(type):
    """
    Copied from: https://stackoverflow.com/questions/6760685/
    """
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Logger(object, metaclass=Singleton):
    def __init__(self, log_file_path="test_file.log"):
        log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(funcName)s(%(lineno)d) %(message)s')

        my_handler = RotatingFileHandler(log_file_path, mode='a', maxBytes=5*1024*1024, backupCount=2, encoding=None, delay=0)
        my_handler.setFormatter(log_formatter)
        my_handler.setLevel(logging.INFO)

        self.app_log = logging.getLogger('root')
        self.app_log.setLevel(logging.INFO)

        self.app_log.addHandler(my_handler)

    def warn(self, log_string):
        self.app_log.log(level=logging.WARN, msg=log_string)

    def info(self, log_string):
        self.app_log.log(level=logging.INFO, msg=log_string)

    def error(self, log_string):
        self.app_log.log(level=logging.ERROR, msg=log_string)


warn = Logger().warn
info = Logger().info
error = Logger().error
