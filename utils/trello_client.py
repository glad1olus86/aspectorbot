"""Клиент для работы с Trello API."""

import aiohttp
from loguru import logger

from config import config


class TrelloClient:
    """Клиент для взаимодействия с Trello API."""

    BASE_URL = "https://api.trello.com/1"

    def __init__(self) -> None:
        """Инициализировать клиент с конфигурацией."""
        self.api_key = config.TRELLO_API_KEY
        self.token = config.TRELLO_TOKEN
        self.board_id = config.TRELLO_BOARD_ID
        self.list_id = config.TRELLO_LIST_ID

    async def create_card(
        self, title: str, description: str
    ) -> dict | None:
        """
        Создать карточку в Trello.

        Args:
            title: Заголовок карточки
            description: Описание карточки

        Returns:
            Данные созданной карточки или None при ошибке
        """
        logger.info(f"=== TrelloClient.create_card: title={title}")
        
        if not all([self.api_key, self.token, self.list_id]):
            logger.error("Trello API не настроен (проверьте .env)")
            return None

        url = f"{self.BASE_URL}/cards"
        params = {
            "key": self.api_key,
            "token": self.token,
            "name": title,
            "desc": description,
            "idList": self.list_id,
        }
        
        logger.info(f"Trello API request: POST {url}")
        logger.debug(f"Params: key={self.api_key[:8]}..., token={self.token[:8]}..., idList={self.list_id}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, params=params) as response:
                    logger.info(f"Trello API response status: {response.status}")
                    if response.status == 200:
                        card_data = await response.json()
                        card_url = f"https://trello.com/c/{card_data.get('shortLink', '')}"
                        logger.info(
                            f"Карточка создана: {card_data.get('name')} — {card_url}"
                        )
                        return {
                            "id": card_data.get("id"),
                            "name": card_data.get("name"),
                            "description": card_data.get("desc", ""),
                            "url": card_url,
                            "shortLink": card_data.get("shortLink"),
                        }
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"Ошибка Trello API: {response.status} — {error_text}"
                        )
                        return None

        except Exception as e:
            logger.error(f"Ошибка при создании карточки в Trello: {e}", exc_info=True)
            return None

    async def add_attachment(
        self, card_id: str, filename: str, file_data: bytes
    ) -> bool:
        """
        Загрузить файл как вложение к карточке Trello.

        Args:
            card_id: ID карточки в Trello
            filename: Имя файла для вложения
            file_data: Бинарные данные файла

        Returns:
            True если вложение успешно создано
        """
        if not all([self.api_key, self.token]):
            logger.error("Trello API не настроен")
            return False

        url = f"{self.BASE_URL}/cards/{card_id}/attachments"
        params = {
            "key": self.api_key,
            "token": self.token,
        }

        form_data = aiohttp.FormData()
        form_data.add_field(
            "file",
            file_data,
            filename=filename,
            content_type="image/jpeg",
        )

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, params=params, data=form_data) as response:
                    if response.status == 200:
                        logger.info(f"Вложение '{filename}' загружено в карточку {card_id}")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"Ошибка загрузки вложения: {response.status} — {error_text}"
                        )
                        return False

        except Exception as e:
            logger.error("Ошибка при загрузке вложения в Trello: {}", e, exc_info=True)
            return False

    async def get_board_lists(self) -> list[dict] | None:
        """
        Получить все списки доски.

        Returns:
            Список словарей с информацией о списках или None при ошибке
        """
        if not all([self.api_key, self.token, self.board_id]):
            logger.error("Trello API не настроен (проверьте .env)")
            return None

        url = f"{self.BASE_URL}/boards/{self.board_id}/lists"
        params = {
            "key": self.api_key,
            "token": self.token,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"Ошибка Trello API: {response.status} — {error_text}"
                        )
                        return None

        except Exception as e:
            logger.error(f"Ошибка при получении списков доски: {e}")
            return None


# Глобальный экземпляр клиента
trello_client = TrelloClient()
