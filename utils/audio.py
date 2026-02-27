"""Утилиты для работы с аудио."""

import asyncio
from pathlib import Path

from loguru import logger

from config import config


async def ogg_to_wav(input_path: Path | str, output_path: Path | str) -> Path:
    """
    Конвертировать OGG/Opus в WAV (16kHz, моно, PCM 16-bit).

    Args:
        input_path: Путь к входному OGG файлу
        output_path: Путь для выходного WAV файла

    Returns:
        Путь к сконвертированному WAV файлу
    """
    input_path = Path(input_path)
    output_path = Path(output_path)

    logger.debug(f"Конвертация аудио: {input_path} → {output_path}")

    # Создаём директорию если не существует
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # FFmpeg команда для конвертации
    cmd = [
        "ffmpeg",
        "-y",  # Перезаписать выходной файл если существует
        "-i", str(input_path),  # Входной файл
        "-ar", "16000",  # Частота дискретизации 16kHz
        "-ac", "1",  # Моно
        "-sample_fmt", "s16",  # PCM 16-bit
        str(output_path),  # Выходной файл
    ]

    process = await asyncio.subprocess.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        error_msg = stderr.decode() if stderr else "Неизвестная ошибка ffmpeg"
        logger.error(f"Ошибка конвертации аудио: {error_msg}")
        raise RuntimeError(f"FFmpeg вернул код {process.returncode}: {error_msg}")

    logger.debug(f"Аудио сконвертировано: {output_path}")
    return output_path


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


__all__ = ["ogg_to_wav", "cleanup_audio_file"]
