"""Simple file logger. Does not write API keys."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from src.config import PROJECT_ROOT

LOG_DIR = PROJECT_ROOT / "logs"
LOG_PATH = LOG_DIR / "mediguide.log"

_configured = False


def get_logger(name: str = "mediguide") -> logging.Logger:
    global _configured
    logger = logging.getLogger(name)
    if not _configured:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        logger.setLevel(logging.INFO)
        handler = RotatingFileHandler(LOG_PATH, maxBytes=512_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)
        _configured = True
    return logger
