"""Определение языка голосового сообщения."""

import asyncio
import json
import wave
from pathlib import Path

from vosk import KaldiRecognizer, Model

from config import config
from loguru import logger
from stt.recognizer import recognizer


class LanguageDetector:
    """
    Определение языка с помощью проб через Vosk модели.

    Прогоняет первые PROBE_DURATION_SEC секунд аудио через
    small-версии всех моделей и выбирает язык с максимальной
    уверенностью.
    """

    def __init__(self) -> None:
        """Инициализировать детектор языка."""
        self._probe_duration = config.PROBE_DURATION_SEC
        self._confidence_threshold = config.CONFIDENCE_THRESHOLD
        logger.info(
            f"LanguageDetector инициализирован: порог={self._confidence_threshold}, "
            f"длительность пробы={self._probe_duration} сек"
        )

    async def detect(self, wav_path: Path | str) -> str | None:
        """
        Определить язык аудиофайла.

        Args:
            wav_path: Путь к WAV файлу

        Returns:
            Код языка или None если не удалось определить
        """
        wav_path = Path(wav_path)

        if not wav_path.exists():
            logger.error(f"WAV файл не найден: {wav_path}")
            return None

        models = recognizer._models
        if not models:
            logger.error("Нет доступных моделей для определения языка")
            return None

        logger.debug(f"Определение языка для {wav_path}")

        # Запускаем в отдельном потоке (CPU-bound операция)
        return await asyncio.to_thread(self._detect_sync, str(wav_path), models)

    def _detect_sync(
        self, wav_path: str, models: dict[str, Model]
    ) -> str | None:
        """
        Синхронное определение языка (выполняется в отдельном потоке).

        Args:
            wav_path: Путь к WAV файлу
            models: Словарь загруженных моделей

        Returns:
            Код языка или None
        """
        try:
            with wave.open(wav_path, "rb") as wf:
                # Вычисляем количество фреймов для пробы
                framerate = wf.getframerate()
                probe_frames = framerate * self._probe_duration

                results: dict[str, float] = {}

                for lang_code, model in models.items():
                    # Сбрасываем файл в начало для каждой модели
                    wf.setpos(0)

                    rec = KaldiRecognizer(model, framerate)
                    rec.SetWords(True)

                    confidence_sum = 0.0
                    confidence_count = 0
                    frames_read = 0

                    while frames_read < probe_frames:
                        data = wf.readframes(4000)
                        if len(data) == 0:
                            break

                        frames_read += len(data) // (wf.getsampwidth() * wf.getnchannels())

                        if rec.AcceptWaveform(data):
                            result = json.loads(rec.Result())
                            if "result" in result:
                                for item in result["result"]:
                                    if "conf" in item:
                                        confidence_sum += item["conf"]
                                        confidence_count += 1

                    # Финальный результат для этой модели
                    final_result = json.loads(rec.FinalResult())
                    if "result" in final_result:
                        for item in final_result["result"]:
                            if "conf" in item:
                                confidence_sum += item["conf"]
                                confidence_count += 1

                    # Средняя уверенность для этого языка
                    avg_confidence = (
                        confidence_sum / confidence_count if confidence_count > 0 else 0.0
                    )
                    results[lang_code] = avg_confidence

                    logger.debug(
                        f"Проба {lang_code}: уверенность={avg_confidence:.3f}"
                    )

                # Выбираем язык с максимальной уверенностью
                if not results:
                    logger.warning("Не удалось получить результаты проб")
                    return None

                best_lang = max(results, key=results.get)
                best_confidence = results[best_lang]

                logger.info(
                    f"Определён язык: {best_lang} (уверенность: {best_confidence:.3f})"
                )

                # Проверяем порог уверенности
                if best_confidence < self._confidence_threshold:
                    logger.info(
                        f"Уверенность {best_confidence:.3f} ниже порога {self._confidence_threshold}"
                    )
                    return None

                return best_lang

        except Exception as e:
            logger.error(f"Ошибка определения языка: {e}")
            return None


# Глобальный экземпляр
language_detector = LanguageDetector()

__all__ = ["LanguageDetector", "language_detector"]
