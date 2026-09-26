"""Opt-in logging for the ``wahlwerk`` package.

Every module logs to its own ``logging.getLogger(__name__)``, all children of the
``wahlwerk`` package logger. The package attaches only a ``NullHandler``, so nothing is
printed or written until :func:`setup_logger` is called: a library must not configure
logging for its users.

Logging is diagnostics only. No result may depend on it; how a result was derived
belongs in a trace, not in the log.
"""

from __future__ import annotations

import logging
from pathlib import Path

__all__ = ["LOGGER_NAME", "disable_logging", "setup_logger"]

LOGGER_NAME = "wahlwerk"
"""The package logger every module logger descends from."""

_FORMAT = "%(asctime)s %(levelname)-8s %(name)s %(message)s"

_LEVELS = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
    "NOTSET": logging.NOTSET,
}


def setup_logger(
    file_path: str | Path | None = None,
    *,
    level: int | str = logging.INFO,
    console: bool = True,
) -> logging.Logger:
    """Configure the ``wahlwerk`` package logger and return it.

    ``setup_logger()`` logs to the console; ``setup_logger("run.log")`` also logs to
    that file, overwriting it. No file is written unless one is given.

    Replaces any handlers set by an earlier call. The logger does not propagate to the
    root logger, so the caller's own logging configuration is left alone.

    ``level`` is a :mod:`logging` constant or its name (``"DEBUG"``, case-insensitive).
    ``console`` logs to ``stderr``.
    """
    if isinstance(file_path, str) and file_path.upper() in _LEVELS:
        raise ValueError(
            f"{file_path!r} is a log level, not a file; pass level={file_path!r}"
        )
    if isinstance(level, str):
        if level.upper() not in _LEVELS:
            raise ValueError(f"unknown log level {level!r}, expected one of {list(_LEVELS)}")
        level = _LEVELS[level.upper()]

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    logger.propagate = False

    formatter = logging.Formatter(_FORMAT)
    handlers: list[logging.Handler] = []
    if console:
        handlers.append(logging.StreamHandler())
    if file_path is not None:
        file_path = Path(file_path)
        handlers.append(logging.FileHandler(file_path, mode="w", encoding="utf-8"))
    if not handlers:
        handlers.append(logging.NullHandler())
    for handler in handlers:
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def disable_logging() -> None:
    """Silence all ``wahlwerk`` log output; :func:`setup_logger` turns it back on."""
    logging.getLogger(LOGGER_NAME).setLevel(logging.CRITICAL + 1)
