"""Хранилище языковых предпочтений пользователей."""

from loguru import logger


class UserLangStore:
    """
    In-memory хранилище выбранного языка для каждого пользователя.

    Ключ — user_id (int), значение — код языка (str) или None (авто).
    При перезапуске бота все предпочтения сбрасываются.
    """

    def __init__(self) -> None:
        self._prefs: dict[int, str] = {}  # user_id -> lang_code

    def set(self, user_id: int, lang_code: str) -> None:
        """Установить предпочтительный язык для пользователя."""
        self._prefs[user_id] = lang_code
        logger.info(f"Язык пользователя {user_id} установлен: {lang_code}")

    def get(self, user_id: int) -> str | None:
        """Получить предпочтительный язык пользователя (None = авто)."""
        return self._prefs.get(user_id)

    def reset(self, user_id: int) -> None:
        """Сбросить предпочтение (вернуть автоопределение)."""
        removed = self._prefs.pop(user_id, None)
        if removed:
            logger.info(f"Язык пользователя {user_id} сброшен (был: {removed})")


# Глобальный экземпляр
user_lang_store = UserLangStore()

__all__ = ["UserLangStore", "user_lang_store"]
