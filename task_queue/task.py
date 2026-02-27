"""Модель задачи для обработки голосовых сообщений."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class TaskStatus(str, Enum):
    """Статусы задачи обработки голосового сообщения."""

    QUEUED = "queued"
    PROCESSING = "processing"
    PENDING_LANG = "pending_lang"
    DONE = "done"
    FAILED = "failed"


@dataclass
class VoiceTask:
    """
    Модель одной задачи распознавания голосового сообщения.

    Attributes:
        task_id: UUID задачи (ключ в PendingStore и в callback_data)
        chat_id: ID чата (группа или личка)
        message_id: ID сообщения с ГС (для reply)
        file_id: Telegram file_id голосового сообщения
        wav_path: Путь к WAV файлу (заполняется при обработке)
        lang: Язык (None = определять автоматически)
        status: Текущий статус задачи
        created_at: Время создания задачи
        user_id: ID пользователя, отправившего ГС
        username: Username пользователя (для отображения кто выбрал язык)
    """

    task_id: str
    chat_id: int
    message_id: int
    file_id: str
    wav_path: str | None = None
    lang: str | None = None
    status: TaskStatus = TaskStatus.QUEUED
    created_at: datetime = field(default_factory=datetime.now)
    user_id: int | None = None
    username: str | None = None
    action: str = "create"  # "create" или "edit"
    action_data: dict | None = None  # Данные для действия (например, {"card_id": "12345"})

    def set_status(self, status: TaskStatus) -> None:
        """Установить статус задачи."""
        self.status = status

    def set_language(self, lang: str) -> None:
        """Установить язык задачи."""
        self.lang = lang

    def set_wav_path(self, wav_path: str) -> None:
        """Установить путь к WAV файлу."""
        self.wav_path = wav_path


__all__ = ["VoiceTask", "TaskStatus"]
