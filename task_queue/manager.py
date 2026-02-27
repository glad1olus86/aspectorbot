"""Менеджер очереди задач."""

import asyncio
import time
import uuid
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from loguru import logger

from bot.keyboards import create_language_keyboard, create_trello_confirm_keyboard
from bot.handlers.trello import _store_card
from bot.messages import get_error_message, get_pending_language_message, get_success_message, get_trello_card_message, get_trello_generating_message, get_trello_error_message
from config import config
from task_queue.task import TaskStatus, VoiceTask
from stt.lang_detector import language_detector
from stt.recognizer import recognizer
from storage.pending import pending_store
from storage.user_lang import user_lang_store
from storage.user_photos import user_photo_store
from utils.audio import cleanup_audio_file, ogg_to_wav


class QueueManager:
    """
    Менеджер очереди задач обработки голосовых сообщений.

    Запускает N воркеров которые параллельно обрабатывают задачи.
    Использует семафор для ограничения параллельных распознаваний Vosk.
    """

    def __init__(self, bot: Bot) -> None:
        """
        Инициализировать менеджер очереди.

        Args:
            bot: Экземпляр бота для отправки сообщений
        """
        self.bot = bot
        self.queue: asyncio.Queue[VoiceTask] = asyncio.Queue()
        self._semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_RECOGNITION)
        self._workers: list[asyncio.Task] = []
        self._running = False

        logger.info(
            f"QueueManager инициализирован: воркеров={config.WORKER_COUNT}, "
            f"max_concurrent={config.MAX_CONCURRENT_RECOGNITION}"
        )

    async def start(self) -> None:
        """Запустить воркеры очереди."""
        self._running = True

        for i in range(config.WORKER_COUNT):
            worker = asyncio.create_task(self._worker(i))
            self._workers.append(worker)

        logger.info(f"Запущено {config.WORKER_COUNT} воркеров очереди")

    async def stop(self) -> None:
        """Остановить воркеры очереди."""
        self._running = False

        # Отменяем все задачи в очереди
        while not self.queue.empty():
            try:
                task = self.queue.get_nowait()
                task.set_status(TaskStatus.FAILED)
            except asyncio.QueueEmpty:
                break

        # Отменяем воркеры
        for worker in self._workers:
            worker.cancel()

        # Ждем завершения
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

        logger.info("Воркеры очереди остановлены")

    async def add_task(self, task: VoiceTask) -> None:
        """
        Добавить задачу в очередь.

        Args:
            task: Задача для добавления
        """
        await self.queue.put(task)
        logger.debug(f"Задача {task.task_id} добавлена в очередь (размер: {self.queue.qsize()})")

    async def _worker(self, worker_id: int) -> None:
        """
        Воркер обработки задач.

        Args:
            worker_id: ID воркера для логирования
        """
        logger.info(f"Воркер {worker_id} запущен")

        while self._running:
            try:
                # Получаем задачу из очереди
                task = await self.queue.get()

                if not self._running:
                    break

                logger.debug(f"Воркер {worker_id} взял задачу {task.task_id}")

                # Обрабатываем задачу
                await self._process_task(task, worker_id)

                # Помечаем задачу как выполненную
                self.queue.task_done()

            except asyncio.CancelledError:
                logger.debug(f"Воркер {worker_id} остановлен")
                break
            except Exception as e:
                logger.error(f"Воркер {worker_id} ошибка: {e}")

        logger.info(f"Воркер {worker_id} завершён")

    async def _process_task(self, task: VoiceTask, worker_id: int) -> None:
        """
        Обработать одну задачу.

        Args:
            task: Задача для обработки
            worker_id: ID воркера
        """
        start_time = time.time()

        try:
            task.set_status(TaskStatus.PROCESSING)

            # Ограничиваем параллельные распознавания
            async with self._semaphore:
                # Скачиваем файл
                logger.info(f"[{worker_id}] Загрузка файла для {task.task_id}")
                ogg_path = await self._download_file(task.file_id)

                try:
                    # Конвертируем в WAV
                    logger.info(f"[{worker_id}] Конвертация в WAV: {task.task_id}")
                    wav_path = await ogg_to_wav(ogg_path, config.TEMP_DIR / f"{task.task_id}.wav")
                    task.set_wav_path(str(wav_path))

                    # Определяем язык если не указан
                    if task.lang is None:
                        # Проверяем предпочтение пользователя
                        if task.user_id:
                            user_pref = user_lang_store.get(task.user_id)
                            if user_pref:
                                task.lang = user_pref
                                logger.info(f"[{worker_id}] Язык из предпочтений: {user_pref} (user={task.user_id})")

                    if task.lang is None:
                        logger.info(f"[{worker_id}] Определение языка: {task.task_id}")
                        task.lang = await language_detector.detect(wav_path)

                        if task.lang is None:
                            # Не удалось определить язык
                            logger.info(f"[{worker_id}] Язык не определён: {task.task_id}")
                            await self._handle_pending_language(task)
                            return

                    # Распознаём речь
                    logger.info(f"[{worker_id}] Распознавание ({task.lang}): {task.task_id}")
                    result = await recognizer.recognize(wav_path, task.lang)

                    processing_time = time.time() - start_time

                    if result.get("text"):
                        # Успех
                        logger.info(
                            f"[{worker_id}] Успех: {task.task_id} -> '{result['text'][:50]}...'"
                            if len(result["text"]) > 50
                            else f"[{worker_id}] Успех: {task.task_id} -> '{result['text']}'"
                        )
                        logger.info(f"[{worker_id}] Вызов _send_result для {task.task_id}")
                        await self._send_result(task, result, processing_time)
                        logger.info(f"[{worker_id}] _send_result завершён, установка статуса DONE")
                        task.set_status(TaskStatus.DONE)
                    else:
                        # Пустой результат
                        logger.warning(f"[{worker_id}] Пустой результат: {task.task_id}")
                        await self._send_error(task)
                        task.set_status(TaskStatus.FAILED)

                finally:
                    # Очищаем временные файлы
                    await cleanup_audio_file(ogg_path)
                    if task.wav_path:
                        await cleanup_audio_file(task.wav_path)

        except Exception as e:
            logger.error(f"[{worker_id}] Ошибка обработки {task.task_id}: {e}")
            task.set_status(TaskStatus.FAILED)
            try:
                await self._send_error(task)
            except Exception as send_error:
                logger.error(f"Не удалось отправить ошибку: {send_error}")

    async def _download_file(self, file_id: str) -> Path:
        """
        Скачать файл из Telegram.

        Args:
            file_id: Telegram file_id

        Returns:
            Путь к скачанному файлу
        """
        config.TEMP_DIR.mkdir(parents=True, exist_ok=True)
        file_path = config.TEMP_DIR / f"{uuid.uuid4()}.ogg"

        file = await self.bot.get_file(file_id)
        await self.bot.download_file(file.file_path, file_path)

        return file_path

    async def _handle_pending_language(self, task: VoiceTask) -> None:
        """
        Обработать задачу с неопределённым языком.

        Отправляет сообщение с кнопками выбора языка и сохраняет задачу в PendingStore.

        Args:
            task: Задача
        """
        # Сохраняем в PendingStore
        pending_store.store(task)

        # Отправляем сообщение с кнопками
        text = get_pending_language_message()
        keyboard = create_language_keyboard(task.task_id)

        try:
            await self.bot.send_message(
                chat_id=task.chat_id,
                text=text,
                reply_to_message_id=task.message_id,
                reply_markup=keyboard,
            )
            logger.info(f"Отправлено сообщение с выбором языка для {task.task_id}")
        except TelegramBadRequest as e:
            logger.error(f"Не удалось отправить сообщение с кнопками: {e}")
            # Удаляем из хранилища если не удалось отправить
            pending_store.remove(task.task_id)

    async def _send_result(
        self, task: VoiceTask, result: dict, processing_time: float
    ) -> None:
        """
        Отправить результат распознавания и выполнить запрошенное действие (создание или редактирование).

        Args:
            task: Задача
            result: Результат распознавания
            processing_time: Время обработки
        """
        logger.info(f"=== _send_result: action={task.action}, task_id={task.task_id}, text={result['text'][:50]}...")

        # Если действие - редактирование карточки
        if task.action == "edit":
            await self._handle_edit_action(task, result, processing_time)
            return

        # Иначе - стандартное создание (create)

        # Определяем был ли ручной выбор языка
        manual = task.task_id in pending_store._claimed or pending_store.get_claimer(task.task_id) is not None
        username = pending_store.get_claimer(task.task_id)

        # Собираем фотографии за последние 3 минуты
        photo_file_ids = []
        if task.user_id:
            photo_file_ids = user_photo_store.collect(task.chat_id, task.user_id)
            if photo_file_ids:
                logger.info(f"Собрано {len(photo_file_ids)} фото для задачи {task.task_id}")

        # Пробуем сразу сформировать задачу через Gemini
        if config.GEMINI_API_KEY:
            try:
                # Отправляем сообщение о генерации
                generating_msg = await self.bot.send_message(
                    chat_id=task.chat_id,
                    text=get_trello_generating_message(),
                    reply_to_message_id=task.message_id,
                )

                # Генерируем задачу через Gemini
                from utils.trello_gemini import generate_trello_card
                logger.info(f"Вызов Gemini для задачи {task.task_id}")
                card_data = generate_trello_card(result["text"])
                logger.info(f"Gemini вернул: {card_data}")

                # Удаляем сообщение о генерации
                try:
                    await generating_msg.delete()
                except Exception:
                    pass

                if card_data:
                    # Добавляем photo_file_ids к данным задачи
                    card_data["photo_file_ids"] = photo_file_ids

                    # Сохраняем задачу в памяти
                    card_id = _store_card(card_data)
                    logger.info(f"Задача сохранена: card_id={card_id}, title={card_data['title']}")

                    # Отправляем задачу с кнопками подтверждения
                    keyboard = create_trello_confirm_keyboard(card_id)
                    await self.bot.send_message(
                        chat_id=task.chat_id,
                        text=get_trello_card_message(card_data["title"], card_data["description"]),
                        reply_to_message_id=task.message_id,
                        reply_markup=keyboard,
                    )
                    logger.info(f"Задача отправлена пользователю")
                    return
                else:
                    logger.warning(f"Gemini не смог сформировать задачу, отправляем только расшифровку")
            except Exception as e:
                logger.error(f"Ошибка при вызове Gemini: {e}")
                # При ошибке просто отправляем расшифровку
                try:
                    await generating_msg.delete()
                except Exception:
                    pass

        # Fallback: если Gemini не настроен или ошибка — отправляем только расшифровку
        text = get_success_message(
            text=result["text"],
            lang=task.lang or "unknown",
            processing_time=processing_time,
            manual=manual,
            username=username,
        )

        try:
            logger.info(f"Отправка расшифровки в чат {task.chat_id}")
            await self.bot.send_message(
                chat_id=task.chat_id,
                text=text,
                reply_to_message_id=task.message_id,
            )
            logger.info(f"Расшифровка отправлена")
        except TelegramBadRequest as e:
            logger.error(f"Не удалось отправить результат: {e}")

    async def _handle_edit_action(self, task: VoiceTask, result: dict, processing_time: float) -> None:
        """
        Обработка действия "Редактирование задачи" (вызывается из _send_result).
        """
        logger.info(f"=== _handle_edit_action: task_id={task.task_id}")
        card_id = task.action_data.get("card_id") if task.action_data else None
        
        if not card_id:
            logger.error("Нет card_id в task.action_data")
            await self._send_error(task)
            return

        from bot.handlers.trello import _get_card, _pending_cards
        original_card_data = _get_card(card_id)

        if not original_card_data:
            logger.error(f"Карточка не найдена: card_id={card_id}")
            await self._send_error(task)
            return

        # Если распознавание пустое (тишина)
        if not result.get("text"):
            await self.bot.send_message(
                chat_id=task.chat_id,
                text="⚠️ Не удалось распознать речь для правок. Попробуйте записать аудио четче.",
                reply_to_message_id=task.message_id
            )
            return

        # Отправляем сообщение о генерации
        generating_msg = await self.bot.send_message(
            chat_id=task.chat_id,
            text=get_trello_generating_message(),
            reply_to_message_id=task.message_id,
        )

        from utils.trello_gemini import edit_trello_card
        # Редактируем карточку через Gemini
        edited_card_data = edit_trello_card(original_card_data, result["text"])

        try:
            await generating_msg.delete()
        except Exception:
            pass

        if not edited_card_data:
            await self._send_error(task)
            return

        # Сохраняем фото файлы из оригинала
        edited_card_data["photo_file_ids"] = original_card_data.get("photo_file_ids", [])
        
        # Обновляем в хранилище
        _pending_cards[card_id] = edited_card_data

        # Отправляем обновлённую карточку с кнопкой "✅ В Trello"
        keyboard = create_trello_confirm_keyboard(card_id)
        await self.bot.send_message(
            chat_id=task.chat_id,
            text=get_trello_card_message(
                edited_card_data["title"],
                edited_card_data["description"]
            ),
            reply_to_message_id=task.message_id,
            reply_markup=keyboard,
        )

    async def _send_error(self, task: VoiceTask) -> None:
        """
        Отправить сообщение об ошибке.

        Args:
            task: Задача
        """
        text = get_error_message()

        try:
            await self.bot.send_message(
                chat_id=task.chat_id,
                text=text,
                reply_to_message_id=task.message_id,
            )
        except TelegramBadRequest as e:
            logger.error(f"Не удалось отправить ошибку: {e}")


# Глобальная переменная для экземпляра (создаётся в main.py)
queue_manager: QueueManager | None = None


def get_queue_manager() -> QueueManager:
    """Получить глобальный экземпляр QueueManager."""
    if queue_manager is None:
        raise RuntimeError("QueueManager не инициализирован")
    return queue_manager


__all__ = ["QueueManager", "queue_manager", "get_queue_manager"]
