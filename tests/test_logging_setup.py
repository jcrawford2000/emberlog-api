import logging
from pathlib import Path

from emberlog_api.app.core.settings import settings
from emberlog_api.utils.loggersetup import configure_logging


def test_configure_logging_adds_ws_payload_file_handler(monkeypatch, tmp_path):
    log_path = tmp_path / "ws-payload.log"
    monkeypatch.setattr(settings, "ws_payload_log_enabled", True)
    monkeypatch.setattr(settings, "ws_payload_log_path", str(log_path))
    monkeypatch.setattr(settings, "enable_file_logging", False)
    monkeypatch.setattr(settings, "log_format", "json")

    configure_logging()

    ws_logger = logging.getLogger("emberlog_api.stats.ws_payload")
    handlers = [h for h in ws_logger.handlers if isinstance(h, logging.FileHandler)]
    assert handlers
    assert Path(handlers[0].baseFilename) == log_path
