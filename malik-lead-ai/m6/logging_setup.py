"""M6 — logging setup (console + append-only file log)."""

from __future__ import annotations

import logging
from pathlib import Path

M6_LOGGER_NAME = "m6"

_FILE_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
_CONSOLE_FORMAT = "%(levelname)s [%(name)s] %(message)s"


def get_logger() -> logging.Logger:
    return logging.getLogger(M6_LOGGER_NAME)


def configure_run_logging(log_path: Path, *, level: int = logging.INFO) -> logging.Logger:
    """Attach an append-only file handler to the M6 logger (idempotent)."""
    logger = get_logger()
    logger.setLevel(level)

    if not any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
               for h in logger.handlers):
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter(_CONSOLE_FORMAT, datefmt="%H:%M:%S"))
        logger.addHandler(console)

    log_path.parent.mkdir(parents=True, exist_ok=True)
    resolved = str(log_path.resolve())
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler) and handler.baseFilename == resolved:
            return logger

    file_handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(_FILE_FORMAT, datefmt="%Y-%m-%dT%H:%M:%S%z"))
    logger.addHandler(file_handler)
    logger.propagate = False
    return logger


__all__ = ["M6_LOGGER_NAME", "get_logger", "configure_run_logging"]
