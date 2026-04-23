"""
config/logger.py
──────────────────────────────────────────────────────────────
Centralized logging setup using Loguru.

Why Loguru over stdlib logging?
  • Zero-config structured output (timestamp, level, caller)
  • Automatic log rotation and retention
  • One import, works everywhere

Usage:
    from config.logger import logger
    logger.info("Agent started")
    logger.error("Tool failed: {error}", error=str(e))
──────────────────────────────────────────────────────────────
"""

import sys
from pathlib import Path
from loguru import logger
from config.settings import settings

# ── Remove default loguru handler ────────────────────────────
logger.remove()

# ── Console handler ───────────────────────────────────────────
# Coloured, human-readable output for development
logger.add(
    sys.stdout,
    level=settings.log_level,
    format=(
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{line}</cyan> | "
        "{message}"
    ),
    colorize=True,
)

# ── File handler ──────────────────────────────────────────────
# Structured logs written to logs/app.log, rotated daily
log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)

logger.add(
    log_dir / "app.log",
    level=settings.log_level,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} | {message}",
    rotation="1 day",       # New file every day
    retention="7 days",     # Keep 7 days of history
    compression="zip",      # Compress old logs
    encoding="utf-8",
)

# ── Export ────────────────────────────────────────────────────
# Re-export the configured logger so every module just does:
# from config.logger import logger
__all__ = ["logger"]