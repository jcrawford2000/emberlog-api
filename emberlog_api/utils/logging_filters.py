import logging

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
