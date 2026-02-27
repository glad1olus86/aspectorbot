"""Логирование для Aspector STT."""

import sys
from pathlib import Path

from loguru import logger

from config import config


def setup_logger() -> None:
    """Настроить логгер."""
    # Создаём директорию для логов если не существует
    config.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Удаляем стандартный обработчик
    logger.remove()

    # Добавляем консольный вывод
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=config.LOG_LEVEL,
        colorize=True,
    )

    # Добавляем файловый вывод
    logger.add(
        config.LOG_FILE,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=config.LOG_LEVEL,
        rotation="10 MB",
        retention="7 days",
        compression="zip",
    )

    logger.info("Логгер настроен")


__all__ = ["logger", "setup_logger"]
