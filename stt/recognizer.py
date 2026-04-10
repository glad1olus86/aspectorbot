"""Распознавание речи через Groq Whisper API."""

from pathlib import Path
from typing import Any

from groq import Groq
from loguru import logger

from config import config


class GroqRecognizer:
    """
    Распознавание речи через Groq API (whisper-large-v3).

    Отправляет аудиофайл напрямую в Groq — без локальных моделей,
    без конвертации (API принимает OGG).
    """

    def __init__(self) -> None:
        """Инициализировать клиент Groq."""
        self._client = Groq(api_key=config.GROQ_API_KEY)
        logger.info("GroqRecognizer инициализирован (whisper-large-v3)")

    def recognize_sync(self, audio_path: Path | str) -> dict[str, Any]:
        """
        Распознать речь из аудиофайла через Groq API (синхронный вызов).

        Вызывается из воркера через asyncio.to_thread().

        Args:
            audio_path: Путь к аудиофайлу (OGG, WAV, MP3 и др.)

        Returns:
            Словарь с ключами:
                - text: распознанный текст
                - lang: определённый язык
        """
        audio_path = Path(audio_path)

        if not audio_path.exists():
            logger.error(f"Аудиофайл не найден: {audio_path}")
            return {"text": "", "lang": "", "error": "Файл не найден"}

        try:
            with open(audio_path, "rb") as f:
                transcription = self._client.audio.transcriptions.create(
                    file=(audio_path.name, f.read()),
                    model="whisper-large-v3",
                    temperature=0,
                    response_format="verbose_json",
                )

            text = transcription.text or ""
            lang = getattr(transcription, "language", "") or ""

            logger.debug(
                f"Распознано ({lang}): '{text[:50]}...'"
                if len(text) > 50
                else f"Распознано ({lang}): '{text}'"
            )

            return {"text": text, "lang": lang}

        except Exception as e:
            logger.error(f"Ошибка распознавания Groq: {e}")
            return {"text": "", "lang": "", "error": str(e)}


# Глобальный экземпляр
recognizer = GroqRecognizer()

__all__ = ["GroqRecognizer", "recognizer"]
