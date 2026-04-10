"""Утилиты для работы с аудио."""

from pathlib import Path

from loguru import logger


async def cleanup_audio_file(file_path: Path | str) -> None:
    """
    Удалить временный аудиофайл.

    Args:
        file_path: Путь к файлу для удаления
    """
    file_path = Path(file_path)
    try:
        if file_path.exists():
            file_path.unlink()
            logger.debug(f"Удалён временный файл: {file_path}")
    except Exception as e:
        logger.warning(f"Не удалось удалить временный файл {file_path}: {e}")


__all__ = ["cleanup_audio_file"]
