"""Распознавание речи с помощью Vosk."""

import asyncio
import json
from pathlib import Path
from typing import Any

from vosk import KaldiRecognizer, Model

from config import config
from loguru import logger


class VoskRecognizer:
    """
    Распознавание речи с использованием Vosk.

    Модели загружаются в память при инициализации и кэшируются
    для последующего использования.
    """

    def __init__(self) -> None:
        """Инициализировать распознаватель и загрузить модели."""
        self._models: dict[str, Model] = {}
        self._load_models()

    def _load_models(self) -> None:
        """Загрузить все модели в память."""
        languages = config.SUPPORTED_LANGUAGES

        for lang_code in languages.keys():
            try:
                model_path = config.get_model_path(lang_code)
                logger.info(f"Загрузка модели для {lang_code}: {model_path}")

                if not model_path.exists():
                    logger.error(f"Модель не найдена: {model_path}")
                    logger.error(
                        f"Скачайте модель в {model_path} - см. инструкцию в README"
                    )
                    continue

                model = Model(model_path=str(model_path))
                self._models[lang_code] = model
                logger.info(f"Модель {lang_code} загружена успешно")

            except Exception as e:
                logger.error(f"Ошибка загрузки модели {lang_code}: {e}")

        if not self._models:
            logger.error("Ни одна модель не загружена! Бот не сможет работать.")

    def get_model(self, lang_code: str) -> Model | None:
        """
        Получить модель для языка.

        Args:
            lang_code: Код языка

        Returns:
            Модель или None если не найдена
        """
        return self._models.get(lang_code)

    async def recognize(
        self, wav_path: Path | str, lang_code: str | None = None
    ) -> dict[str, Any]:
        """
        Распознать речь из WAV файла.

        Args:
            wav_path: Путь к WAV файлу
            lang_code: Код языка (None = автоопределение через первую модель)

        Returns:
            Словарь с ключами:
                - text: распознанный текст
                - confidence: уверенность (0.0-1.0)
                - lang: использованный язык
        """
        wav_path = Path(wav_path)

        if not wav_path.exists():
            logger.error(f"WAV файл не найден: {wav_path}")
            return {"text": "", "confidence": 0.0, "lang": "", "error": "Файл не найден"}

        # Если язык не указан, используем первую доступную модель
        if lang_code is None:
            if not self._models:
                logger.error("Нет доступных моделей для распознавания")
                return {"text": "", "confidence": 0.0, "lang": "", "error": "Нет моделей"}
            lang_code = list(self._models.keys())[0]
            logger.debug(f"Язык не указан, используем: {lang_code}")

        model = self.get_model(lang_code)
        if model is None:
            logger.error(f"Модель для языка {lang_code} не найдена")
            return {
                "text": "",
                "confidence": 0.0,
                "lang": lang_code,
                "error": f"Модель {lang_code} не найдена",
            }

        # Запускаем распознавание в отдельном потоке (CPU-bound операция)
        return await asyncio.to_thread(self._recognize_sync, str(wav_path), model, lang_code)

    def _recognize_sync(
        self, wav_path: str, model: Model, lang_code: str
    ) -> dict[str, Any]:
        """
        Синхронное распознавание (выполняется в отдельном потоке).

        Args:
            wav_path: Путь к WAV файлу
            model: Vosk модель
            lang_code: Код языка

        Returns:
            Словарь с результатами распознавания
        """
        import wave

        try:
            with wave.open(wav_path, "rb") as wf:
                # Проверяем параметры аудио
                if wf.getnchannels() != 1 or wf.getframerate() != 16000:
                    logger.warning(
                        f"Некорректные параметры аудио: channels={wf.getnchannels()}, rate={wf.getframerate()}"
                    )

                rec = KaldiRecognizer(model, wf.getframerate())
                rec.SetWords(True)

                full_text = []
                confidence_sum = 0.0
                confidence_count = 0

                while True:
                    data = wf.readframes(4000)
                    if len(data) == 0:
                        break

                    if rec.AcceptWaveform(data):
                        result = json.loads(rec.Result())
                        if "text" in result and result["text"]:
                            full_text.append(result["text"])
                        if "result" in result:
                            for item in result["result"]:
                                if "conf" in item:
                                    confidence_sum += item["conf"]
                                    confidence_count += 1

                # Финальный результат
                final_result = json.loads(rec.FinalResult())
                if "text" in final_result and final_result["text"]:
                    full_text.append(final_result["text"])

                # Вычисляем среднюю уверенность
                avg_confidence = (
                    confidence_sum / confidence_count if confidence_count > 0 else 0.0
                )

                text = " ".join(full_text).strip()

                logger.debug(
                    f"Распознано ({lang_code}): '{text[:50]}...' confidence={avg_confidence:.2f}"
                    if len(text) > 50
                    else f"Распознано ({lang_code}): '{text}' confidence={avg_confidence:.2f}"
                )

                return {
                    "text": text,
                    "confidence": avg_confidence,
                    "lang": lang_code,
                }

        except Exception as e:
            logger.error(f"Ошибка распознавания: {e}")
            return {"text": "", "confidence": 0.0, "lang": lang_code, "error": str(e)}


# Глобальный экземпляр
recognizer = VoskRecognizer()

__all__ = ["VoskRecognizer", "recognizer"]
