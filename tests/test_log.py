import logging

import pytest

import wahlwerk
from wahlwerk.log import LOGGER_NAME, disable_logging, setup_logger


@pytest.fixture(autouse=True)
def restore_package_logger():
    """setup_logger changes a process-wide logger; put it back after each test."""
    logger = logging.getLogger(LOGGER_NAME)
    handlers, level, propagate = list(logger.handlers), logger.level, logger.propagate
    yield
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        if handler not in handlers:
            handler.close()
    for handler in handlers:
        logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = propagate


def test_package_is_silent_by_default():
    handlers = logging.getLogger(LOGGER_NAME).handlers
    assert any(isinstance(h, logging.NullHandler) for h in handlers)
    assert not any(isinstance(h, logging.StreamHandler) for h in handlers)


def test_setup_logger_is_exported_from_the_root():
    assert wahlwerk.setup_logger is setup_logger
    assert wahlwerk.disable_logging is disable_logging


def test_setup_logger_writes_a_file_only_when_asked(tmp_path):
    log_file = tmp_path / "run.log"
    logger = setup_logger(log_file, level="debug", console=False)
    logging.getLogger("wahlwerk.state.chamber").debug("hello %s", "world")
    for handler in logger.handlers:
        handler.flush()
    text = log_file.read_text(encoding="utf-8")
    assert "DEBUG" in text
    assert "wahlwerk.state.chamber hello world" in text


def test_setup_logger_accepts_str_path(tmp_path):
    logger = setup_logger(str(tmp_path / "run.log"), console=False)
    assert any(isinstance(h, logging.FileHandler) for h in logger.handlers)


def test_setup_logger_replaces_handlers():
    logger = setup_logger()
    setup_logger()
    assert len(logger.handlers) == 1
    assert logger.propagate is False


def test_setup_logger_without_output_is_silent():
    logger = setup_logger(console=False)
    assert all(isinstance(h, logging.NullHandler) for h in logger.handlers)


@pytest.mark.parametrize(("given", "expected"), [("info", logging.INFO), ("DEBUG", logging.DEBUG), (logging.WARNING, logging.WARNING)])
def test_setup_logger_levels(given, expected):
    assert setup_logger(level=given, console=False).level == expected


def test_unknown_level_is_rejected():
    with pytest.raises(ValueError, match="unknown log level 'loud'"):
        setup_logger(level="loud")


def test_disable_logging(tmp_path):
    log_file = tmp_path / "run.log"
    setup_logger(log_file, level="debug", console=False)
    disable_logging()
    logging.getLogger("wahlwerk.io").critical("should not appear")
    assert log_file.read_text(encoding="utf-8") == ""


def test_path_is_the_first_argument(tmp_path):
    log_file = tmp_path / "run.log"
    logger = setup_logger(log_file)
    assert any(isinstance(h, logging.FileHandler) for h in logger.handlers)
    assert any(type(h) is logging.StreamHandler for h in logger.handlers)


def test_level_name_as_path_is_rejected():
    """``setup_logger("debug")`` would otherwise write a file called ``debug``."""
    with pytest.raises(ValueError, match="'debug' is a log level, not a file; pass level='debug'"):
        setup_logger("debug")
