import json
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional

from loguru import logger
from config import config


@dataclass
class Contact:
    """Модель контакта."""
    id: str
    name: str
    username: str
    trigger_words: list[str] = field(default_factory=list)
    tasks_sent: int = 0


class ContactsStore:
    """Хранилище контактов (owner_id -> List[Contact]). JSON based."""

    _instance = None
    _file_path = Path(config.BASE_DIR) / "data" / "contacts.json"

    def __new__(cls) -> "ContactsStore":
        if cls._instance is None:
            cls._instance = super(ContactsStore, cls).__new__(cls)
            cls._instance._data = {}  # type: dict[str, list[Contact]]
            cls._instance._load()
        return cls._instance

    def _load(self) -> None:
        if not self._file_path.exists():
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            self._data = {}
            return

        try:
            with open(self._file_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)

            self._data = {}
            for owner_id, contacts_list in raw_data.items():
                self._data[owner_id] = [
                    Contact(
                        id=c["id"],
                        name=c["name"],
                        username=c["username"],
                        trigger_words=c.get("trigger_words", []),
                        tasks_sent=c.get("tasks_sent", 0),
                    )
                    for c in contacts_list
                ]
        except Exception as e:
            logger.error(f"Ошибка загрузки контактов: {e}")
            self._data = {}

    def _save(self) -> None:
        try:
            self._file_path.parent.mkdir(parents=True, exist_ok=True)

            raw_data = {
                owner_id: [asdict(c) for c in contacts]
                for owner_id, contacts in self._data.items()
            }

            temp_path = self._file_path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(raw_data, f, ensure_ascii=False, indent=2)
            temp_path.replace(self._file_path)

        except Exception as e:
            logger.error(f"Ошибка сохранения контактов: {e}")

    def add_contact(self, owner_id: int, name: str, username: str, trigger_words: list[str] | None = None) -> Contact:
        """Добавить новый контакт."""
        owner_str = str(owner_id)
        if owner_str not in self._data:
            self._data[owner_str] = []

        clean_username = username.lstrip("@")

        # Нормализуем триггер-слова: lowercase, strip
        triggers = [w.strip().lower() for w in (trigger_words or []) if w.strip()]

        contact = Contact(
            id=uuid.uuid4().hex[:8],
            name=name,
            username=clean_username,
            trigger_words=triggers,
        )
        self._data[owner_str].append(contact)
        self._save()

        logger.info(f"Контакт добавлен: {name} (@{clean_username}), триггеры={triggers}, owner={owner_id}")
        return contact

    def get_contacts(self, owner_id: int) -> List[Contact]:
        """Получить все контакты пользователя."""
        return self._data.get(str(owner_id), [])

    def get_contact(self, owner_id: int, contact_id: str) -> Optional[Contact]:
        """Получить конкретный контакт."""
        for contact in self.get_contacts(owner_id):
            if contact.id == contact_id:
                return contact
        return None

    def get_triggers_map(self, owner_id: int) -> list[dict[str, str]]:
        """
        Получить маппинг триггер-слов → username для промта LLM.

        Returns:
            [{"username": "@vasya", "name": "Василий", "triggers": ["вася", "василий", "васька"]}, ...]
        """
        result = []
        for contact in self.get_contacts(owner_id):
            if contact.trigger_words:
                result.append({
                    "username": f"@{contact.username}",
                    "name": contact.name,
                    "triggers": contact.trigger_words,
                })
        return result

    def increment_stats(self, owner_id: int, contact_id: str) -> None:
        """Увеличить счетчик отправленных задач (tasks_sent) на 1."""
        contact = self.get_contact(owner_id, contact_id)
        if contact:
            contact.tasks_sent += 1
            self._save()
            logger.debug(f"Статистика контакта {contact_id} обновлена: {contact.tasks_sent}")


# Глобальный экземпляр
contacts_store = ContactsStore()

__all__ = ["Contact", "ContactsStore", "contacts_store"]
