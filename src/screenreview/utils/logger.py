# -*- coding: utf-8 -*-
"""Simple logger factory for file + console logging."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path


def get_logger(name: str, log_file: str | Path | None = None) -> logging.Logger:
    """Return a configured logger instance."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%dT%H:%M:%S")

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    if log_file is not None:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def setup_session_logging(base_dir: str | Path, app_name: str) -> Path | None:
    """Configure root logging for the app and optionally write a session log file.

    Logging to file is enabled when DEBUG is truthy in the environment.
    """
    root = logging.getLogger()
    if getattr(root, "_screenreview_logging_configured", False):
        return getattr(root, "_screenreview_session_log", None)

    debug_enabled = _env_bool("DEBUG", False)
    level = logging.DEBUG  # force debug trace
    root.setLevel(level)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%dT%H:%M:%S")

    if not any(isinstance(handler, logging.StreamHandler) for handler in root.handlers):
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(level)
        stream_handler.setFormatter(formatter)
        root.addHandler(stream_handler)

    session_log_path: Path | None = None
    if debug_enabled:
        logs_dir = Path(base_dir) / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        safe_app_name = app_name.lower().replace(" ", "-")
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        session_log_path = logs_dir / f"{safe_app_name}-session-{timestamp}.log"
        file_handler = logging.FileHandler(session_log_path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
        root.info("Debug logging enabled. Session log file: %s", session_log_path)
    else:
        # User requested detailed logging always to debug this issue
        logs_dir = Path(base_dir) / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        safe_app_name = app_name.lower().replace(" ", "-")
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        session_log_path = logs_dir / f"{safe_app_name}-session-forced-{timestamp}.log"
        file_handler = logging.FileHandler(session_log_path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
        root.info("Session logging forced ON for deep trace. Session log file: %s", session_log_path)

    root._screenreview_logging_configured = True  # type: ignore[attr-defined]
    root._screenreview_session_log = session_log_path  # type: ignore[attr-defined]
    return session_log_path
