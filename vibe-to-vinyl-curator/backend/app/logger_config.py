"""Logging configuration for the Vibe-to-Vinyl Curator backend."""

import logging
import sys
from pathlib import Path
from typing import Final


LOG_DIR: Final[Path] = Path(__file__).resolve().parents[1] / "logs"
LOG_FILE: Final[Path] = LOG_DIR / "app.log"


def configure_logging(level: int = logging.INFO) -> None:
    """Configure application logging to both console and backend/logs/app.log."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s"
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
