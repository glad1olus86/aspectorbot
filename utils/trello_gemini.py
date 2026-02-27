"""Модуль для работы с Gemini API — генерация задач из голосовых сообщений."""

import json

from google import genai
from google.genai import types
from loguru import logger

from config import config

# Системный промт для генерации задачи
GENERATE_CARD_PROMPT = """Ты помощник для создания задач из голосовых сообщений.

ВАЖНО: Текст ниже получен через автоматическое распознавание речи (STT) и может содержать ошибки.
Распознаватель часто искажает слова — особенно сленг, сокращения и IT-термины.
Исправляй очевидные ошибки распознавания, восстанавливая смысл из контекста.

Примеры типичных ошибок STT:
- "от тэйсти" → "оттестить" (протестировать)
- "за деплой ить" → "задеплоить" (выложить на сервер)
- "гит хаб" → "GitHub"
- "рефак торинг" → "рефакторинг"
- "апи ай" → "API"
- "фронт энд" → "фронтенд"

Требования:
1. Сначала исправь ошибки распознавания и восстанови реальный смысл сказанного
2. Определи название проекта из контекста (например, если речь о Jobsi — проект Jobsi)
3. Создай краткий заголовок задачи (до 100 символов)
4. Создай подробное описание задачи (2-5 предложений)
5. Формат ответа — СТРОГО JSON с полями: title, description

Пример ответа:
{{
    "title": "Jobsi — Интеграция новой платёжной системы",
    "description": "Необходимо интегрировать платёжную систему CloudPayments на сайт Jobsi. Включает настройку эквайринга, тестирование платежей, обработку webhook'ов."
}}

Текст голосового сообщения:
{text}
"""

# Промт для редактирования задачи
EDIT_CARD_PROMPT = """Ты помощник для редактирования задач.

У тебя есть исходная задача и правки от пользователя.
Примени правки к задаче и верни обновлённую версию.

Формат ответа — СТРОГО JSON с полями: title, description

Исходная задача:
{original}

Правки пользователя:
{edits}

Обновлённая задача:
"""


def _create_client() -> genai.Client:
    """Создать клиент Gemini API."""
    return genai.Client(api_key=config.GEMINI_API_KEY)


def _parse_card(response_text: str) -> dict[str, str] | None:
    """Распарсить ответ Gemini в данные задачи."""
    try:
        result = json.loads(response_text)
    except json.JSONDecodeError as e:
        logger.error(f"Не удалось распарсить JSON: {e}, ответ: {response_text[:300]}")
        return None

    if "title" not in result or "description" not in result:
        logger.error(f"Некорректный формат ответа: {result}")
        return None

    return {"title": result["title"], "description": result["description"]}


def generate_trello_card(text: str) -> dict[str, str] | None:
    """
    Сгенерировать задачу из текста голосового сообщения через Gemini.

    Args:
        text: Распознанный текст голосового сообщения

    Returns:
        Словарь с полями title и description или None при ошибке
    """
    logger.info(f"=== generate_trello_card: входной текст ({len(text)} chars): {text[:100]}...")

    if not config.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY не настроен")
        return None

    try:
        client = _create_client()
        prompt = GENERATE_CARD_PROMPT.format(text=text)

        logger.info("Генерация ответа через Gemini...")
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )

        if not response.text:
            logger.error("Gemini вернул пустой ответ")
            return None

        logger.debug(f"Raw Gemini response: {response.text[:300]}")

        card = _parse_card(response.text)
        if card:
            logger.info(f"Gemini сгенерировал задачу: {card['title']}")
        return card

    except Exception as e:
        logger.error("Ошибка при генерации карточки через Gemini: {}", e, exc_info=True)
        return None


def edit_trello_card(original: dict[str, str], edits: str) -> dict[str, str] | None:
    """
    Отредактировать задачу по правкам пользователя через Gemini.

    Args:
        original: Исходная задача с полями title и description
        edits: Текст правок от пользователя

    Returns:
        Обновлённая задача с полями title и description или None при ошибке
    """
    if not config.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY не настроен")
        return None

    try:
        client = _create_client()
        prompt = EDIT_CARD_PROMPT.format(
            original=f"Заголовок задачи: {original['title']}\nОписание задачи: {original['description']}",
            edits=edits,
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )

        if not response.text:
            logger.error("Gemini вернул пустой ответ при редактировании")
            return None

        card = _parse_card(response.text)
        if card:
            logger.info(f"Gemini отредактировал задачу: {card['title']}")
        return card

    except Exception as e:
        logger.error("Ошибка при редактировании карточки через Gemini: {}", e, exc_info=True)
        return None
