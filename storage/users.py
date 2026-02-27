import json
import os
from pathlib import Path
from loguru import logger

from config import config

class UserRegistry:
    """Одиночка для хранения сопоставления username -> chat_id."""
    
    _instance = None
    _file_path = Path(config.BASE_DIR) / "data" / "users.json"
    
    def __new__(cls) -> "UserRegistry":
        if cls._instance is None:
            cls._instance = super(UserRegistry, cls).__new__(cls)
            cls._instance._users = {}  # type: dict[str, int]
            cls._instance._load()
        return cls._instance
        
    def _load(self) -> None:
        """Загрузить пользователей из файла."""
        if not self._file_path.exists():
            # Создаем директорию, если нет
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            self._users = {}
            return
            
        try:
            with open(self._file_path, "r", encoding="utf-8") as f:
                self._users = json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки пользователей: {e}")
            self._users = {}

    def _save(self) -> None:
        """Сохранить пользователей в файл."""
        try:
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self._file_path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self._users, f, ensure_ascii=False, indent=2)
            temp_path.replace(self._file_path)
        except Exception as e:
            logger.error(f"Ошибка сохранения пользователей: {e}")

    def register(self, username: str, chat_id: int) -> None:
        """
        Регистрирует или обновляет связь username -> chat_id.
        
        Args:
            username: Telegram username без '@'.
            chat_id: ID чата (личного).
        """
        if not username:
            return
            
        clean_username = username.lstrip("@").lower()
        
        # Обновляем только если изменился ID или пользователя не было
        if self._users.get(clean_username) != chat_id:
            self._users[clean_username] = chat_id
            self._save()
            logger.debug(f"Пользователь @{clean_username} зарегистрирован с chat_id={chat_id}")

    def get_chat_id(self, username: str) -> int | None:
        """Получить chat_id по username."""
        clean_username = username.lstrip("@").lower()
        return self._users.get(clean_username)


# Глобальный экземпляр
user_registry = UserRegistry()

__all__ = ["UserRegistry", "user_registry"]
