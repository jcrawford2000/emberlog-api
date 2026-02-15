import logging

from emberlog_api.utils.log_context import get_conn_id, get_request_id


class ClassMethodFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        parts = record.name.split(".")
        class_name = parts[-1] if parts else "?"
        record.class_method = f"{class_name}.{record.funcName}"
        return True


class LoggerIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Attach a contextual id if present (see LoggerAdapter below)
        record.logger_id = getattr(record, "logger_id", "-")
        return True


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = getattr(record, "request_id", get_request_id())
        record.conn_id = getattr(record, "conn_id", get_conn_id())
        return True
