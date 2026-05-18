"""logger.py のローテーション設定検証."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler


def test_logger_has_rotating_file_handler() -> None:
    """get_logger で取得した logger に RotatingFileHandler が含まれる."""
    logging.Logger.manager.loggerDict.pop("test_rotation_logger", None)

    from app.shared.logger import get_logger

    logger = get_logger("test_rotation_logger")
    rotators = [h for h in logger.handlers if isinstance(h, RotatingFileHandler)]
    assert len(rotators) >= 1, f"RotatingFileHandler が見つからない: {logger.handlers}"

    rotator = rotators[0]
    # 5 MB × 5 世代
    assert rotator.maxBytes == 5 * 1024 * 1024
    assert rotator.backupCount == 5


def test_logger_handlers_include_stream() -> None:
    """標準出力 handler も併用される."""
    logging.Logger.manager.loggerDict.pop("test_stream_logger", None)

    from app.shared.logger import get_logger

    logger = get_logger("test_stream_logger")
    stream_handlers = [
        h
        for h in logger.handlers
        if isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler)
    ]
    assert len(stream_handlers) >= 1


def test_logger_is_idempotent_for_same_name() -> None:
    """同じ name で 2 回呼んでも handler が増えない."""
    logging.Logger.manager.loggerDict.pop("test_idempotent_logger", None)

    from app.shared.logger import get_logger

    logger1 = get_logger("test_idempotent_logger")
    handlers_count_1 = len(logger1.handlers)
    logger2 = get_logger("test_idempotent_logger")
    assert logger1 is logger2
    assert len(logger2.handlers) == handlers_count_1
