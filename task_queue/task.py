"""Модель задачи для обработки голосовых сообщений."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class TaskStatus(str, Enum):
    """Статусы задачи обработки голосового сообщения."""

    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


@dataclass
class VoiceTask:
    """
    Модель одной задачи распознавания голосового сообщения.

    Attributes:
        task_id: UUID задачи
        chat_id: ID чата (группа или личка)
        message_id: ID сообщения с ГС (для reply)
        file_id: Telegram file_id голосового сообщения
        lang: Язык (заполняется из ответа Groq)
        status: Текущий статус задачи
        created_at: Время создания задачи
        user_id: ID пользователя, отправившего ГС
        username: Username пользователя
        action: "create" или "edit" (для Trello)
        action_data: Данные для действия (например, {"card_id": "12345"})
    """

    task_id: str
    chat_id: int
    message_id: int
    file_id: str
    lang: str | None = None
    status: TaskStatus = TaskStatus.QUEUED
    created_at: datetime = field(default_factory=datetime.now)
    user_id: int | None = None
    username: str | None = None
    action: str = "create"
    action_data: dict | None = None

    def set_status(self, status: TaskStatus) -> None:
        """Установить статус задачи."""
        self.status = status


__all__ = ["VoiceTask", "TaskStatus"]
