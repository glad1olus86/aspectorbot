"""Конфигурация проекта Aspector STT."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Конфигурация приложения."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Telegram
    BOT_TOKEN: str

    # Groq API (Whisper STT)
    GROQ_API_KEY: str

    # Пути
    BASE_DIR: Path = Path(".")
    TEMP_DIR: Path = Path("tmp/audio")

    # Очередь
    WORKER_COUNT: int = 3
    QUEUE_NOTIFY_THRESHOLD: int = 5

    # Логирование
    LOG_LEVEL: str = "INFO"
    LOG_FILE: Path = Path("logs/aspector.log")

    # Провайдер генерации карточек: "gemini" или "groq"
    CARD_PROVIDER: str = "gemini"

    # Gemini API
    GEMINI_API_KEY: str = ""

    # Группа разработчиков (chat_id для отправки задач)
    GROUP_CHAT_ID: int = 0

    # Напоминания о дедлайнах
    REMINDER_ENABLED: bool = True
    REMINDER_CHECK_INTERVAL_MINUTES: int = 5
    REMINDER_COOLDOWN_MINUTES: int = 60

    # Trello API
    TRELLO_API_KEY: str = ""
    TRELLO_TOKEN: str = ""
    TRELLO_BOARD_ID: str = ""
    TRELLO_LIST_ID: str = ""

    def __init__(self, **kwargs):
        """Инициализация конфигурации с вычислением абсолютных путей."""
        super().__init__(**kwargs)
        self._base_dir = self.BASE_DIR.resolve() if self.BASE_DIR else Path(".").resolve()
        self.TEMP_DIR = self._base_dir / self.TEMP_DIR
        self.LOG_FILE = self._base_dir / self.LOG_FILE


config = Config()
