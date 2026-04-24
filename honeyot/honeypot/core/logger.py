"""
core/logger.py — Logging JSON estructurado
Honeypot VM203 · SOC honeycos
"""

import logging
import logging.handlers
import json
import os
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """Formateador que emite cada registro como una línea JSON."""

    SKIP_FIELDS = {
        "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno",
        "funcName", "created", "msecs", "relativeCreated", "thread",
        "threadName", "processName", "process", "name", "message",
        # Evitar que campos extra con estos nombres pisen los calculados
        "timestamp", "level",
    }

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()

        # timestamp y level siempre calculados desde el LogRecord
        data: dict = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc)
                         .strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "level": record.levelname,
        }

        # Campos extra añadidos con logger.info("msg", extra={...})
        for key, value in record.__dict__.items():
            if key not in self.SKIP_FIELDS and not key.startswith("_"):
                data[key] = value

        # message siempre al final
        data["message"] = record.message

        return json.dumps(data, ensure_ascii=False)


def setup_logger(cfg: dict) -> logging.Logger:
    """Configura y devuelve el logger global."""
    log_path: str = cfg["logging"]["path"]
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=cfg["logging"]["max_bytes"],
        backupCount=cfg["logging"]["backup_count"],
        encoding="utf-8",
    )
    handler.setFormatter(JsonFormatter())

    # También a consola (recogido por journald vía systemd)
    console = logging.StreamHandler()
    console.setFormatter(JsonFormatter())

    logger = logging.getLogger("honeypot")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.addHandler(console)
    logger.propagate = False

    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger("honeypot")
