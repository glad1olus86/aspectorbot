"""Хранилище задач, ожидающих выбора языка."""

import time
from datetime import datetime, timedelta

from loguru import logger

from config import config
from task_queue.task import TaskStatus, VoiceTask


class PendingStore:
    """
    In-memory хранилище задач в статусе PENDING_LANG.

    Хранит задачи в памяти по task_id. При перезапуске бота
    все задачи теряются.

    Автоматически очищает устаревшие записи по TTL.
    """

    def __init__(self) -> None:
        """Инициализировать хранилище."""
        self._tasks: dict[str, VoiceTask] = {}
        self._claimed: dict[str, str] = {}  # task_id -> username кто нажал
        self._ttl_seconds = config.PENDING_TTL_MINUTES * 60
        logger.info(f"PendingStore инициализирован, TTL: {config.PENDING_TTL_MINUTES} мин")

    def store(self, task: VoiceTask) -> None:
        """
        Сохранить задачу в хранилище.

        Args:
            task: Задача для сохранения
        """
        task.set_status(TaskStatus.PENDING_LANG)
        self._tasks[task.task_id] = task
        logger.debug(f"Задача {task.task_id} сохранена в PendingStore")

    def claim(self, task_id: str, username: str | None = None) -> bool:
        """
        Атомарно зарезервировать задачу (пометить как "выбирается язык").

        Args:
            task_id: ID задачи
            username: Username пользователя который нажал кнопку

        Returns:
            True если задача успешно зарезервирована, False если уже занята или не найдена
        """
        if task_id not in self._tasks:
            logger.debug(f"Задача {task_id} не найдена в PendingStore")
            return False

        if task_id in self._claimed:
            logger.debug(f"Задача {task_id} уже зарезервирована пользователем {self._claimed[task_id]}")
            return False

        self._claimed[task_id] = username or "unknown"
        logger.debug(f"Задача {task_id} зарезервирована пользователем {username}")
        return True

    def resolve(self, task_id: str, lang: str) -> VoiceTask | None:
        """
        Получить задачу и установить выбранный язык.

        Args:
            task_id: ID задачи
            lang: Выбранный код языка

        Returns:
            Задача с установленным языком или None если не найдена
        """
        if task_id not in self._tasks:
            logger.debug(f"Задача {task_id} не найдена в PendingStore")
            return None

        task = self._tasks.pop(task_id)
        self._claimed.pop(task_id, None)

        task.set_language(lang)
        task.set_status(TaskStatus.QUEUED)

        logger.info(f"Задача {task_id} разрешена: язык={lang}")
        return task

    def get(self, task_id: str) -> VoiceTask | None:
        """
        Получить задачу без изменения статуса.

        Args:
            task_id: ID задачи

        Returns:
            Задача или None если не найдена
        """
        return self._tasks.get(task_id)

    def remove(self, task_id: str) -> None:
        """
        Удалить задачу из хранилища.

        Args:
            task_id: ID задачи
        """
        self._tasks.pop(task_id, None)
        self._claimed.pop(task_id, None)
        logger.debug(f"Задача {task_id} удалена из PendingStore")

    def cleanup_expired(self) -> list[str]:
        """
        Очистить устаревшие задачи.

        Returns:
            Список ID удалённых задач
        """
        now = datetime.now()
        expired = []

        for task_id, task in list(self._tasks.items()):
            age = (now - task.created_at).total_seconds()
            if age > self._ttl_seconds:
                expired.append(task_id)
                self.remove(task_id)
                logger.info(f"Задача {task_id} удалена по TTL (возраст: {age:.0f} сек)")

        return expired

    @property
    def size(self) -> int:
        """Количество задач в хранилище."""
        return len(self._tasks)

    def get_claimer(self, task_id: str) -> str | None:
        """
        Получить username пользователя который выбрал язык.

        Args:
            task_id: ID задачи

        Returns:
            Username или None
        """
        return self._claimed.get(task_id)


# Глобальный экземпляр
pending_store = PendingStore()

__all__ = ["PendingStore", "pending_store"]
