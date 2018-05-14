import collections
import logging
import sys

FORMATTER = logging.Formatter('[%(asctime)-15s] [%(threadName)s] [%(levelname)s]: %(message)s')


def pretty_time_delta(seconds):
    sign_string = '-' if seconds < 0 else ''
    seconds = abs(int(seconds))
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if days > 0:
        return '%s%dd%dh%dm%ds' % (sign_string, days, hours, minutes, seconds)
    elif hours > 0:
        return '%s%dh%dm%ds' % (sign_string, hours, minutes, seconds)
    elif minutes > 0:
        return '%s%dm%ds' % (sign_string, minutes, seconds)
    else:
        return '%s%ds' % (sign_string, seconds)


def compare_list(first, second):
    return collections.Counter(first) == collections.Counter(second)


def configure_logging(log_file_name, max_log_size, max_log_file_to_keep, log_level, external_libs_logging_level):
    syslog_handler = logging.StreamHandler(sys.stdout)
    file_handler = logging.handlers.RotatingFileHandler(filename=log_file_name,
                                                        maxBytes=max_log_size,
                                                        backupCount=max_log_file_to_keep,
                                                        encoding='utf-8')
    syslog_handler.setFormatter(FORMATTER)
    file_handler.setFormatter(FORMATTER)

    for logger_name, logger in logging.Logger.manager.loggerDict.items():
        logger.handlers = [syslog_handler, file_handler]
        if logger_name == '__main__' or logger_name == 'lib':
            logger.level = log_level
        else:
            logger.level = external_libs_logging_level

    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.handlers = [syslog_handler, file_handler]
    werkzeug_logger.level = logging.ERROR if external_libs_logging_level == logging.INFO else logging.DEBUG
