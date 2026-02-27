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

    # Пути к моделям
    # BASE_DIR — корневая директория проекта (по умолчанию = директория запуска)
    BASE_DIR: Path = Path(".")
    # Остальные пути строятся относительно BASE_DIR
    MODELS_DIR: Path = Path("stt/models")
    MODEL_RU: str = "vosk-model-ru-0.42"
    MODEL_EN: str = "vosk-model-en-us-0.22"
    MODEL_UK: str = "vosk-model-uk-v3"
    MODEL_CS: str = "vosk-model-cs-0.4"

    # Параметры определения языка
    CONFIDENCE_THRESHOLD: float = 0.65
    PROBE_DURATION_SEC: int = 5

    # Очередь
    WORKER_COUNT: int = 3
    MAX_CONCURRENT_RECOGNITION: int = 2
    QUEUE_NOTIFY_THRESHOLD: int = 5
    PENDING_TTL_MINUTES: int = 30

    # Временная директория для аудио
    TEMP_DIR: Path = Path("tmp/audio")

    # Логирование
    LOG_LEVEL: str = "INFO"
    LOG_FILE: Path = Path("logs/aspector.log")

    # Gemini API
    GEMINI_API_KEY: str = ""

    # Trello API
    TRELLO_API_KEY: str = ""
    TRELLO_TOKEN: str = ""
    TRELLO_BOARD_ID: str = ""
    TRELLO_LIST_ID: str = ""

    def __init__(self, **kwargs):
        """Инициализация конфигурации с вычислением абсолютных путей."""
        super().__init__(**kwargs)
        # Преобразуем все пути в абсолютные относительно BASE_DIR
        self._base_dir = self.BASE_DIR.resolve() if self.BASE_DIR else Path(".").resolve()
        self.MODELS_DIR = self._base_dir / self.MODELS_DIR
        self.TEMP_DIR = self._base_dir / self.TEMP_DIR
        self.LOG_FILE = self._base_dir / self.LOG_FILE

    # Поддерживаемые языки
    @property
    def SUPPORTED_LANGUAGES(self) -> dict[str, str]:
        """Словарь поддерживаемых языков {код: название}."""
        return {
            "ru": "Русский",
            "en": "English",
            "uk": "Українська",
            "cs": "Čeština",
        }

    @property
    def LANGUAGE_FLAGS(self) -> dict[str, str]:
        """Флаги для языков."""
        return {
            "ru": "🇷🇺",
            "en": "🇺🇸",
            "uk": "🇺🇦",
            "cs": "🇨🇿",
        }

    def get_model_path(self, lang_code: str) -> Path:
        """Получить путь к модели для языка."""
        model_name = getattr(self, f"MODEL_{lang_code.upper()}", None)
        if not model_name:
            raise ValueError(f"Модель для языка {lang_code} не найдена")
        return self.MODELS_DIR / model_name


config = Config()
