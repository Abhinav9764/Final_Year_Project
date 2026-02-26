"""
utils/logger.py
===============
Centralised logging setup for the RAD-ML agent.

Creates a dual-sink logger:
  - Coloured, human-readable output via ``rich`` to the console.
  - Detailed DEBUG-level records appended to a rotating log file.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
from pathlib import Path


def setup_logger(config: dict) -> logging.Logger:
    """
    Configure and return the root logger for RAD-ML.

    Parameters
    ----------
    config : dict
        The ``logging`` section of config.yaml.

    Returns
    -------
    logging.Logger
        Configured root logger.

    Raises
    ------
    OSError
        If the log directory cannot be created.
    """
    log_file: str = config.get("log_file", "logs/rad_ml.log")
    console_level_name: str = config.get("console_level", "INFO").upper()
    file_level_name: str = config.get("file_level", "DEBUG").upper()

    console_level = getattr(logging, console_level_name, logging.INFO)
    file_level = getattr(logging, file_level_name, logging.DEBUG)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)   # Capture everything; handlers filter

    # Avoid duplicate handlers if called more than once
    if root_logger.handlers:
        return root_logger

    # ------------------------------------------------------------------
    # 1. Console sink — uses rich if available, falls back to StreamHandler
    # ------------------------------------------------------------------
    try:
        from rich.logging import RichHandler  # noqa: PLC0415

        console_handler: logging.Handler = RichHandler(
            level=console_level,
            rich_tracebacks=True,
            show_path=False,
            markup=True,
        )
        console_handler.setFormatter(logging.Formatter("%(message)s", datefmt="[%X]"))
    except ImportError:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(console_level)
        console_handler.setFormatter(
            logging.Formatter(
                "[%(asctime)s] %(levelname)-8s %(name)s — %(message)s",
                datefmt="%H:%M:%S",
            )
        )

    root_logger.addHandler(console_handler)

    # ------------------------------------------------------------------
    # 2. File sink — rotating at 5 MB, keeps 3 backups
    # ------------------------------------------------------------------
    try:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(file_level)
        file_handler.setFormatter(
            logging.Formatter(
                "[%(asctime)s] %(levelname)-8s %(name)s — %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        root_logger.addHandler(file_handler)

    except OSError as exc:
        root_logger.warning(
            "Could not create log file at '%s': %s. File logging disabled.",
            log_file,
            exc,
        )

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Return a named child logger (call after ``setup_logger`` has run)."""
    return logging.getLogger(name)
