"""Обработчик голосовых сообщений."""

import uuid
from datetime import datetime

from aiogram import F, Router
from aiogram.types import Message, Voice

from bot.messages import get_queue_message
from config import config
from loguru import logger
from task_queue.manager import QueueManager
from task_queue.task import TaskStatus, VoiceTask

router = Router(name="voice")


@router.message(F.voice)
async def handle_voice(message: Message, queue_manager: QueueManager) -> None:
    """
    Обработчик голосовых сообщений.

    1. Получает голосовое сообщение из Telegram
    2. Создаёт VoiceTask
    3. Кладёт в очередь
    4. При большой очереди отправляет уведомление о позиции
    """
    voice: Voice = message.voice

    # Создаём задачу
    task = VoiceTask(
        task_id=str(uuid.uuid4()),
        chat_id=message.chat.id,
        message_id=message.message_id,
        file_id=voice.file_id,
        status=TaskStatus.QUEUED,
        created_at=datetime.now(),
        user_id=message.from_user.id if message.from_user else None,
        username=message.from_user.username if message.from_user else None,
    )

    logger.info(
        f"Получено ГС: task_id={task.task_id}, chat_id={task.chat_id}, "
        f"duration={voice.duration}сек, user={task.username}"
    )

    # Проверяем размер очереди перед добавлением
    queue_size = queue_manager.queue.qsize()

    # Добавляем в очередь
    await queue_manager.add_task(task)

    # Если очередь большая, отправляем уведомление
    if queue_size >= config.QUEUE_NOTIFY_THRESHOLD:
        position = queue_size + 1  # +1 потому что мы только что добавили
        text = get_queue_message(position)
        await message.answer(text, reply_to_message_id=message.message_id)
        logger.debug(f"Отправлено уведомление о очереди: позиция {position}")


@router.message(F.audio)
async def handle_audio(message: Message, queue_manager: QueueManager) -> None:
    """
    Обработчик аудио сообщений (если пользователь отправил как файл).

    Перенаправляем на тот же обработчик что и голосовые.
    """
    # Создаём фейковый voice объект из audio
    audio = message.audio

    task = VoiceTask(
        task_id=str(uuid.uuid4()),
        chat_id=message.chat.id,
        message_id=message.message_id,
        file_id=audio.file_id,
        status=TaskStatus.QUEUED,
        created_at=datetime.now(),
        user_id=message.from_user.id if message.from_user else None,
        username=message.from_user.username if message.from_user else None,
    )

    logger.info(
        f"Получено аудио (файл): task_id={task.task_id}, chat_id={task.chat_id}, "
        f"user={task.username}"
    )

    await queue_manager.add_task(task)


__all__ = ["router"]
