"""Генерация задач из голосовых сообщений через LLM (Gemini или Groq)."""

import json
import re
from datetime import datetime

from loguru import logger

from config import config

# Названия дней недели на русском
_WEEKDAYS_RU = [
    "понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"
]


def _current_date_context() -> str:
    """Текущая дата и день недели для промта."""
    now = datetime.now()
    weekday = _WEEKDAYS_RU[now.weekday()]
    return f"Сегодня: {weekday}, {now.strftime('%d.%m.%Y %H:%M')}"


def _build_team_section(triggers_map: list[dict]) -> str:
    """Построить секцию команды для промта."""
    if not triggers_map:
        return ""

    lines = []
    for entry in triggers_map:
        triggers = ", ".join(entry["triggers"])
        lines.append(f'- {entry["name"]} ({entry["username"]}): [{triggers}]')

    return (
        "\n\nКоманда (триггер-слова → участник):\n"
        + "\n".join(lines)
        + "\n\n"
        "Если в тексте упоминается кто-то из команды (по триггер-словам выше) — "
        'укажи его username в поле assignee (например "@vasya"). '
        "Если никто не упомянут — assignee = null."
    )


# Системный промт для генерации задачи
GENERATE_CARD_PROMPT = """Ты помощник для создания задач из голосовых сообщений.

{date_context}

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
{team_section}
Требования:
1. Сначала исправь ошибки распознавания и восстанови реальный смысл сказанного
2. Определи название проекта из контекста (например, если речь о Jobsi — проект Jobsi)
3. Создай краткий заголовок задачи (до 100 символов)
4. Создай подробное описание задачи (2-5 предложений)
5. Если в тексте упоминается дедлайн или срок (например "до четверга", "к пятнице", "завтра до обеда", "через 2 дня") — определи точную дату и время дедлайна. Если срок не упоминается — deadline = null
6. Если в тексте упоминается участник команды — укажи его username в поле assignee. Если нет — assignee = null
7. Формат ответа — СТРОГО JSON с полями: title, description, deadline, assignee

Формат deadline: "DD.MM.YYYY HH:MM" (например "12.04.2026 16:00")
Если время не указано явно — ставь 18:00 по умолчанию.

Пример ответа:
{{
    "title": "Jobsi — Интеграция новой платёжной системы",
    "description": "Необходимо интегрировать платёжную систему CloudPayments на сайт Jobsi. Включает настройку эквайринга, тестирование платежей, обработку webhook'ов.",
    "deadline": "14.04.2026 18:00",
    "assignee": "@vasya"
}}

Текст голосового сообщения:
{text}
"""

# Промт для редактирования задачи
EDIT_CARD_PROMPT = """Ты помощник для редактирования задач.

{date_context}

У тебя есть исходная задача и правки от пользователя.
Примени правки к задаче и верни обновлённую версию.

Если правки меняют дедлайн — обнови его. Если нет — оставь прежний.
Если правки меняют исполнителя — обнови assignee. Если нет — оставь прежний.
{team_section}
Формат ответа — СТРОГО JSON с полями: title, description, deadline, assignee
Формат deadline: "DD.MM.YYYY HH:MM" или null если не задан.
assignee: "@username" или null.

Исходная задача:
{original}

Правки пользователя:
{edits}

Обновлённая задача:
"""


def parse_deadline(raw: str | None) -> datetime | None:
    """Распарсить строку дедлайна в datetime."""
    if not raw:
        return None
    for fmt in ("%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    logger.warning(f"Не удалось распарсить дедлайн: {raw}")
    return None


def _parse_card(response_text: str) -> dict | None:
    """Распарсить JSON-ответ LLM в данные задачи."""
    # Пробуем напрямую
    try:
        result = json.loads(response_text)
    except json.JSONDecodeError:
        # Пробуем извлечь JSON из markdown-блока ```json ... ```
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group(1))
            except json.JSONDecodeError as e:
                logger.error(f"Не удалось распарсить JSON из блока: {e}, ответ: {response_text[:300]}")
                return None
        else:
            match = re.search(r"\{[^{}]*\"title\"[^{}]*\}", response_text, re.DOTALL)
            if match:
                try:
                    result = json.loads(match.group(0))
                except json.JSONDecodeError as e:
                    logger.error(f"Не удалось распарсить JSON: {e}, ответ: {response_text[:300]}")
                    return None
            else:
                logger.error(f"JSON не найден в ответе: {response_text[:300]}")
                return None

    if "title" not in result or "description" not in result:
        logger.error(f"Некорректный формат ответа: {result}")
        return None

    # Парсим дедлайн
    deadline = parse_deadline(result.get("deadline"))
    deadline_str = deadline.strftime("%d.%m.%Y %H:%M") if deadline else None

    # Парсим assignee
    assignee = result.get("assignee") or None
    if assignee and not assignee.startswith("@"):
        assignee = f"@{assignee}"

    card = {
        "title": result["title"],
        "description": result["description"],
        "deadline": deadline_str,
        "assignee": assignee,
    }

    if deadline_str:
        logger.info(f"Дедлайн из LLM: {deadline_str}")
    if assignee:
        logger.info(f"Исполнитель из LLM: {assignee}")

    return card


# ─── Gemini ─────────────────────────────────────────────────────────────


def _gemini_generate(text: str, team_section: str) -> dict | None:
    """Сгенерировать задачу через Gemini."""
    from google import genai
    from google.genai import types

    try:
        client = genai.Client(api_key=config.GEMINI_API_KEY)
        prompt = GENERATE_CARD_PROMPT.format(
            date_context=_current_date_context(),
            team_section=team_section,
            text=text,
        )

        logger.info("Генерация через Gemini...")
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
        return _parse_card(response.text)

    except Exception as e:
        logger.error("Ошибка Gemini generate: {}", e, exc_info=True)
        return None


def _gemini_edit(original: dict, edits: str, team_section: str) -> dict | None:
    """Отредактировать задачу через Gemini."""
    from google import genai
    from google.genai import types

    deadline_info = f"\nДедлайн: {original['deadline']}" if original.get("deadline") else ""
    assignee_info = f"\nИсполнитель: {original['assignee']}" if original.get("assignee") else ""

    try:
        client = genai.Client(api_key=config.GEMINI_API_KEY)
        prompt = EDIT_CARD_PROMPT.format(
            date_context=_current_date_context(),
            team_section=team_section,
            original=(
                f"Заголовок задачи: {original['title']}\n"
                f"Описание задачи: {original['description']}"
                f"{deadline_info}{assignee_info}"
            ),
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

        return _parse_card(response.text)

    except Exception as e:
        logger.error("Ошибка Gemini edit: {}", e, exc_info=True)
        return None


# ─── Groq (Llama) ──────────────────────────────────────────────────────

GROQ_CARD_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"


def _groq_generate(text: str, team_section: str) -> dict | None:
    """Сгенерировать задачу через Groq (Llama)."""
    from groq import Groq

    try:
        client = Groq(api_key=config.GROQ_API_KEY)
        prompt = GENERATE_CARD_PROMPT.format(
            date_context=_current_date_context(),
            team_section=team_section,
            text=text,
        )

        logger.info(f"Генерация через Groq ({GROQ_CARD_MODEL})...")
        response = client.chat.completions.create(
            model=GROQ_CARD_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_completion_tokens=1024,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        if not content:
            logger.error("Groq вернул пустой ответ")
            return None

        logger.debug(f"Raw Groq response: {content[:300]}")
        return _parse_card(content)

    except Exception as e:
        logger.error("Ошибка Groq generate: {}", e, exc_info=True)
        return None


def _groq_edit(original: dict, edits: str, team_section: str) -> dict | None:
    """Отредактировать задачу через Groq (Llama)."""
    from groq import Groq

    deadline_info = f"\nДедлайн: {original['deadline']}" if original.get("deadline") else ""
    assignee_info = f"\nИсполнитель: {original['assignee']}" if original.get("assignee") else ""

    try:
        client = Groq(api_key=config.GROQ_API_KEY)
        prompt = EDIT_CARD_PROMPT.format(
            date_context=_current_date_context(),
            team_section=team_section,
            original=(
                f"Заголовок задачи: {original['title']}\n"
                f"Описание задачи: {original['description']}"
                f"{deadline_info}{assignee_info}"
            ),
            edits=edits,
        )

        response = client.chat.completions.create(
            model=GROQ_CARD_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_completion_tokens=1024,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        if not content:
            logger.error("Groq вернул пустой ответ при редактировании")
            return None

        return _parse_card(content)

    except Exception as e:
        logger.error("Ошибка Groq edit: {}", e, exc_info=True)
        return None


# ─── Публичный API (диспетчеризация по config.CARD_PROVIDER) ───────────


def generate_trello_card(text: str, user_id: int | None = None) -> dict | None:
    """
    Сгенерировать задачу из текста голосового сообщения.

    Args:
        text: Распознанный текст
        user_id: ID пользователя (для загрузки триггер-слов контактов)

    Returns:
        {"title": str, "description": str, "deadline": str|None, "assignee": str|None}
    """
    logger.info(f"=== generate_trello_card [{config.CARD_PROVIDER}]: ({len(text)} chars): {text[:100]}...")

    # Подгружаем триггер-слова контактов
    team_section = ""
    if user_id:
        from storage.contacts import contacts_store
        triggers_map = contacts_store.get_triggers_map(user_id)
        team_section = _build_team_section(triggers_map)

    if config.CARD_PROVIDER == "groq":
        card = _groq_generate(text, team_section)
    else:
        card = _gemini_generate(text, team_section)

    if card:
        logger.info(f"Задача: {card['title']}, deadline={card.get('deadline')}, assignee={card.get('assignee')}")
    return card


def edit_trello_card(original: dict, edits: str, user_id: int | None = None) -> dict | None:
    """
    Отредактировать задачу по правкам пользователя.

    Args:
        original: Исходная карточка
        edits: Текст правок
        user_id: ID пользователя (для триггер-слов)

    Returns:
        {"title": str, "description": str, "deadline": str|None, "assignee": str|None}
    """
    team_section = ""
    if user_id:
        from storage.contacts import contacts_store
        triggers_map = contacts_store.get_triggers_map(user_id)
        team_section = _build_team_section(triggers_map)

    if config.CARD_PROVIDER == "groq":
        card = _groq_edit(original, edits, team_section)
    else:
        card = _gemini_edit(original, edits, team_section)

    if card:
        logger.info(f"Отредактировано: {card['title']}, deadline={card.get('deadline')}, assignee={card.get('assignee')}")
    return card
