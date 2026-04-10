"""Хранилище задач, отправленных в группу разработчиков."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from loguru import logger


class GroupTaskStatus(str, Enum):
    """Статусы задачи в группе."""

    PENDING = "pending"        # Ожидает исполнителя
    IN_PROGRESS = "in_progress"  # Взята в работу
    DONE = "done"              # Выполнена


@dataclass
class GroupTask:
    """Задача, отправленная в группу разработчиков."""

    task_id: str                           # Уникальный ID
    title: str
    description: str
    creator_user_id: int                   # Кто создал задачу (для уведомления)
    creator_username: str | None = None
    group_message_id: int | None = None    # ID сообщения в группе (для ссылки)
    status: GroupTaskStatus = GroupTaskStatus.PENDING
    worker_user_id: int | None = None      # Кто взял в работу
    worker_username: str | None = None
    taken_at: datetime | None = None
    deadline: str | None = None              # Строка дедлайна из LLM ("12.04.2026 18:00") или None
    completed_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.now)  # Время отправки в группу
    last_reminder_at: datetime | None = None  # Когда последнее напоминание отправлено
    reminder_stage: str | None = None         # "half" / "urgent" / "overdue"
    photo_file_ids: list[str] = field(default_factory=list)


class GroupTaskStore:
    """In-memory хранилище задач в группе."""

    def __init__(self) -> None:
        self._tasks: dict[str, GroupTask] = {}

    def store(self, task: GroupTask) -> None:
        """Сохранить задачу."""
        self._tasks[task.task_id] = task
        logger.debug(f"GroupTask {task.task_id} сохранена: {task.title}")

    def get(self, task_id: str) -> GroupTask | None:
        """Получить задачу по ID."""
        return self._tasks.get(task_id)

    def take(self, task_id: str, user_id: int, username: str | None) -> bool:
        """
        Взять задачу в работу. Дедлайн уже хранится в задаче (из LLM).

        Returns:
            True если успешно, False если уже занята или не найдена
        """
        task = self._tasks.get(task_id)
        if not task or task.status != GroupTaskStatus.PENDING:
            return False

        task.status = GroupTaskStatus.IN_PROGRESS
        task.worker_user_id = user_id
        task.worker_username = username
        task.taken_at = datetime.now()
        logger.info(f"GroupTask {task_id} взята в работу: @{username}")
        return True

    def get_tasks_needing_reminder(self) -> list[GroupTask]:
        """Получить активные задачи с дедлайном (кандидаты на напоминание)."""
        return [
            t for t in self._tasks.values()
            if t.status in (GroupTaskStatus.PENDING, GroupTaskStatus.IN_PROGRESS)
            and t.deadline is not None
        ]

    def complete(self, task_id: str) -> bool:
        """
        Отметить задачу как выполненную.

        Returns:
            True если успешно, False если не в работе или не найдена
        """
        task = self._tasks.get(task_id)
        if not task or task.status != GroupTaskStatus.IN_PROGRESS:
            return False

        task.status = GroupTaskStatus.DONE
        task.completed_at = datetime.now()
        logger.info(f"GroupTask {task_id} выполнена: @{task.worker_username}")
        return True


# Глобальный экземпляр
group_task_store = GroupTaskStore()

__all__ = ["GroupTask", "GroupTaskStatus", "GroupTaskStore", "group_task_store"]
