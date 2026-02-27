"""Хранилище фотографий пользователей для привязки к карточкам Trello."""

import time
from dataclasses import dataclass

from loguru import logger


@dataclass
class PhotoEntry:
    """Одна фотография от пользователя."""

    file_id: str
    timestamp: float
    consumed: bool = False


class UserPhotoStore:
    """
    In-memory хранилище фотографий, привязанных к (chat_id, user_id).

    Фотографии хранятся с таймстампом. При вызове collect()
    возвращаются только фото за последние 3 минуты.
    Возвращённые фото помечаются как consumed.
    """

    PHOTO_TTL_SECONDS = 180  # 3 минуты
    CLEANUP_THRESHOLD = 100

    def __init__(self) -> None:
        self._photos: dict[tuple[int, int], list[PhotoEntry]] = {}

    def add(self, chat_id: int, user_id: int, file_id: str) -> None:
        """Добавить фотографию от пользователя."""
        key = (chat_id, user_id)
        if key not in self._photos:
            self._photos[key] = []
        self._photos[key].append(PhotoEntry(file_id=file_id, timestamp=time.time()))
        logger.debug(f"Фото добавлено: chat={chat_id}, user={user_id}, total={len(self._photos[key])}")

        if sum(len(v) for v in self._photos.values()) > self.CLEANUP_THRESHOLD:
            self._cleanup_expired()

    def collect(self, chat_id: int, user_id: int) -> list[str]:
        """
        Собрать file_id фотографий за последние 3 минуты.

        Помечает собранные фото как consumed.

        Returns:
            Список file_id фотографий (может быть пустым)
        """
        key = (chat_id, user_id)
        entries = self._photos.get(key, [])

        now = time.time()
        cutoff = now - self.PHOTO_TTL_SECONDS

        result = []
        for entry in entries:
            if entry.timestamp >= cutoff and not entry.consumed:
                entry.consumed = True
                result.append(entry.file_id)

        if result:
            logger.info(f"Собрано {len(result)} фото для chat={chat_id}, user={user_id}")

        return result

    def _cleanup_expired(self) -> None:
        """Удалить все фото старше TTL и все consumed."""
        now = time.time()
        cutoff = now - self.PHOTO_TTL_SECONDS

        for key in list(self._photos.keys()):
            self._photos[key] = [
                e for e in self._photos[key]
                if e.timestamp >= cutoff and not e.consumed
            ]
            if not self._photos[key]:
                del self._photos[key]


# Глобальный экземпляр
user_photo_store = UserPhotoStore()

__all__ = ["UserPhotoStore", "user_photo_store"]
