import logging
import logging.config
from copy import deepcopy

from pythonjsonlogger import jsonlogger
from emberlog_api.app.core.settings import settings

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "dev": {
            "format": "%(asctime)s | %(levelname)-7s | %(logger_id)s | %(class_method)s - %(message)s",
        },
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "fmt": "%(asctime)s %(levelname)s %(name)s %(class_method)s %(logger_id)s %(message)s",
        },
    },
    "filters": {
        "class_method": {"()": "emberlog_api.utils.logging_filters.ClassMethodFilter"},
        "logger_id": {"()": "emberlog_api.utils.logging_filters.LoggerIdFilter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "dev",
            "filters": ["class_method", "logger_id"],
        },
        "file_app": {
            "class": "logging.FileHandler",
            "level": "INFO",
            "filename": "/var/log/emberlog/emberlog_api.log",
            "formatter": "json",
            "filters": ["class_method", "logger_id"],
        },
    },
    "loggers": {
        # Per-module control Example
        # "emberlog_api.app": {
        #     "level": "DEBUG",
        #     "handlers": ["console", "file_app"],
        #     "propagate": False,
        # },
        # Default
        "": {"level": "DEBUG", "handlers": ["console", "file_app"]},
    },
}


def configure_logging():
    config = deepcopy(LOGGING)
    if not settings.enable_file_logging:
        config["handlers"].pop("file_app", None)
        config["loggers"][""]["handlers"] = ["console"]
    logging.config.dictConfig(config)
