import logging
import logging.config
from copy import deepcopy

from emberlog_api.app.core.settings import settings

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "dev": {
            "format": "%(asctime)s | %(levelname)-7s | req=%(request_id)s conn=%(conn_id)s | %(logger_id)s | %(class_method)s - %(message)s",
        },
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "fmt": "%(asctime)s %(levelname)s %(name)s %(class_method)s %(logger_id)s %(request_id)s %(conn_id)s %(message)s",
        },
    },
    "filters": {
        "class_method": {"()": "emberlog_api.utils.logging_filters.ClassMethodFilter"},
        "logger_id": {"()": "emberlog_api.utils.logging_filters.LoggerIdFilter"},
        "request_context": {
            "()": "emberlog_api.utils.logging_filters.RequestContextFilter"
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "dev",
            "filters": ["class_method", "logger_id", "request_context"],
        },
        "file_app": {
            "class": "logging.FileHandler",
            "level": "INFO",
            "filename": "/var/log/emberlog/emberlog_api.log",
            "formatter": "json",
            "filters": ["class_method", "logger_id", "request_context"],
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
    log_format = settings.log_format.strip().lower()
    if log_format == "auto":
        log_format = "json" if settings.emberlog_env.strip().lower() == "prod" else "console"

    if log_format == "json":
        config["handlers"]["console"]["formatter"] = "json"
    else:
        config["handlers"]["console"]["formatter"] = "dev"

    if not settings.enable_file_logging:
        config["handlers"].pop("file_app", None)
        config["loggers"][""]["handlers"] = ["console"]
    logging.config.dictConfig(config)
