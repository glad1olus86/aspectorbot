"""Cron-система напоминаний о дедлайнах групповых задач."""

import asyncio
from datetime import datetime
from enum import Enum

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from loguru import logger

from config import config
from storage.group_tasks import GroupTask, GroupTaskStatus, group_task_store
from utils.trello_llm import parse_deadline


class ReminderStage(str, Enum):
    """Стадии напоминаний (прогрессируют: half → urgent → overdue)."""

    HALF = "half"         # ~50% времени прошло
    URGENT = "urgent"     # ≤3 часа до дедлайна
    OVERDUE = "overdue"   # Дедлайн просрочен


# Порядок стадий для сравнения
_STAGE_ORDER = {None: 0, "half": 1, "urgent": 2, "overdue": 3}

# Названия дней недели
_WEEKDAYS_RU = [
    "понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"
]


def _current_date_context() -> str:
    """Текущая дата и день недели."""
    now = datetime.now()
    weekday = _WEEKDAYS_RU[now.weekday()]
    return f"Сегодня: {weekday}, {now.strftime('%d.%m.%Y %H:%M')}"


# ─── Логика определения стадии ──────────────────────────────────────────


def determine_reminder_stage(task: GroupTask, now: datetime) -> ReminderStage | None:
    """
    Определить нужна ли новая стадия напоминания.

    Returns:
        ReminderStage если нужно отправить напоминание, None если не нужно.
    """
    deadline_dt = parse_deadline(task.deadline)
    if deadline_dt is None:
        return None

    current_order = _STAGE_ORDER.get(task.reminder_stage, 0)

    # Просрочено
    if now >= deadline_dt:
        if current_order < _STAGE_ORDER["overdue"]:
            return ReminderStage.OVERDUE
        return None

    remaining = (deadline_dt - now).total_seconds()

    # Срочно: ≤3 часа
    if remaining <= 3 * 3600:
        if current_order < _STAGE_ORDER["urgent"]:
            return ReminderStage.URGENT
        return None

    # Половина: используем created_at как базу
    total_budget = (deadline_dt - task.created_at).total_seconds()
    if total_budget <= 0:
        return None

    elapsed_ratio = (now - task.created_at).total_seconds() / total_budget
    if elapsed_ratio >= 0.5:
        if current_order < _STAGE_ORDER["half"]:
            return ReminderStage.HALF

    return None


def is_cooldown_elapsed(task: GroupTask, now: datetime, cooldown_minutes: int) -> bool:
    """Проверить прошёл ли cooldown с последнего напоминания."""
    if task.last_reminder_at is None:
        return True
    elapsed = (now - task.last_reminder_at).total_seconds()
    return elapsed >= cooldown_minutes * 60


# ─── Генерация текста через LLM ─────────────────────────────────────────

REMINDER_PROMPT = """Ты — дружелюбный бот-ассистент в рабочем Telegram-чате.

{date_context}

Тебе нужно написать краткое напоминание о задаче. Напоминание должно быть естественным,
не шаблонным, на русском языке. Используй разговорный деловой тон.

Данные задачи:
- Название: {title}
- Описание: {description}
- Дедлайн: {deadline}
- Статус: {status}
- Исполнитель: {worker}
- Автор: {creator}
- Уровень срочности: {urgency}

Правила:
1. Если есть исполнитель — обязательно упомяни его через @username (например @vasya)
2. Если исполнителя нет (задача не взята) — напомни что задача ждёт исполнителя
3. Упомяни название задачи
4. Тон зависит от срочности:
   - "Половина времени прошла" — мягкое дружеское напоминание
   - "Осталось мало времени" — более настойчивое
   - "Дедлайн просрочен" — серьёзное, но конструктивное
5. Длина: 2-4 предложения максимум
6. НЕ используй markdown, пиши обычный текст
7. НЕ начинай сообщение с "Привет" или "Здравствуйте"

Напиши только текст напоминания, без кавычек и пояснений:"""

_URGENCY_LABELS = {
    ReminderStage.HALF: "Половина времени прошла",
    ReminderStage.URGENT: "Осталось мало времени (менее 3 часов)",
    ReminderStage.OVERDUE: "Дедлайн просрочен!",
}

_STATUS_LABELS = {
    GroupTaskStatus.PENDING: "Ожидает исполнителя",
    GroupTaskStatus.IN_PROGRESS: "В работе",
}

# Fallback на случай если LLM недоступен
_FALLBACK_TEMPLATES = {
    ReminderStage.HALF: "Напоминание: задача «{title}» — прошла половина времени до дедлайна ({deadline}). {mention}",
    ReminderStage.URGENT: "Внимание: до дедлайна задачи «{title}» осталось менее 3 часов ({deadline})! {mention}",
    ReminderStage.OVERDUE: "Дедлайн задачи «{title}» ({deadline}) просрочен! {mention}",
}


def _generate_reminder_text(task: GroupTask, stage: ReminderStage) -> str:
    """
    Сгенерировать текст напоминания через LLM.
    При ошибке — fallback на шаблон.
    """
    worker = f"@{task.worker_username}" if task.worker_username else "Не назначен"
    creator = f"@{task.creator_username}" if task.creator_username else "Неизвестный"

    prompt = REMINDER_PROMPT.format(
        date_context=_current_date_context(),
        title=task.title,
        description=task.description,
        deadline=task.deadline,
        status=_STATUS_LABELS.get(task.status, task.status.value),
        worker=worker,
        creator=creator,
        urgency=_URGENCY_LABELS[stage],
    )

    try:
        if config.CARD_PROVIDER == "groq":
            text = _groq_reminder(prompt)
        else:
            text = _gemini_reminder(prompt)

        if text:
            return text
    except Exception as e:
        logger.error(f"Ошибка LLM при генерации напоминания: {e}")

    # Fallback
    mention = worker if task.worker_username else "Задача ждёт исполнителя!"
    return _FALLBACK_TEMPLATES[stage].format(
        title=task.title,
        deadline=task.deadline,
        mention=mention,
    )


def _groq_reminder(prompt: str) -> str | None:
    """Сгенерировать напоминание через Groq."""
    from groq import Groq

    client = Groq(api_key=config.GROQ_API_KEY)
    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_completion_tokens=300,
    )
    return response.choices[0].message.content or None


def _gemini_reminder(prompt: str) -> str | None:
    """Сгенерировать напоминание через Gemini."""
    from google import genai

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    return response.text or None


# ─── Ссылка на сообщение ────────────────────────────────────────────────


def _build_message_link(chat_id: int, message_id: int) -> str:
    """Построить ссылку на сообщение в группе/супергруппе."""
    chat_id_str = str(chat_id)
    if chat_id_str.startswith("-100"):
        short_id = chat_id_str[4:]
    else:
        short_id = chat_id_str.lstrip("-")
    return f"https://t.me/c/{short_id}/{message_id}"


# ─── Отправка напоминания ────────────────────────────────────────────────


async def _send_reminder(bot: Bot, task: GroupTask, text: str) -> None:
    """Отправить напоминание в группу с кнопкой-ссылкой на задачу."""
    # Кнопка "Перейти к задаче"
    keyboard = None
    if task.group_message_id and config.GROUP_CHAT_ID:
        link = _build_message_link(config.GROUP_CHAT_ID, task.group_message_id)
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📋 Перейти к задаче", url=link)]
            ]
        )

    try:
        kwargs = {
            "chat_id": config.GROUP_CHAT_ID,
            "text": text,
            "reply_markup": keyboard,
        }
        # Отвечаем на оригинальное сообщение задачи
        if task.group_message_id:
            kwargs["reply_to_message_id"] = task.group_message_id

        await bot.send_message(**kwargs)

    except TelegramBadRequest as e:
        # Если оригинальное сообщение удалено — отправляем без reply
        if "replied message" in str(e).lower() or "message not found" in str(e).lower():
            logger.warning(f"Оригинальное сообщение задачи {task.task_id} не найдено, отправляем без reply")
            await bot.send_message(
                chat_id=config.GROUP_CHAT_ID,
                text=text,
                reply_markup=keyboard,
            )
        else:
            raise


# ─── Основной loop ──────────────────────────────────────────────────────


async def reminder_loop(bot: Bot) -> None:
    """
    Фоновый цикл проверки дедлайнов и отправки напоминаний.
    Запускается в on_startup через asyncio.create_task().
    """
    logger.info(
        f"Reminder loop запущен: интервал={config.REMINDER_CHECK_INTERVAL_MINUTES} мин, "
        f"cooldown={config.REMINDER_COOLDOWN_MINUTES} мин"
    )

    while True:
        try:
            await asyncio.sleep(config.REMINDER_CHECK_INTERVAL_MINUTES * 60)

            if not config.REMINDER_ENABLED or not config.GROUP_CHAT_ID:
                continue

            now = datetime.now()
            candidates = group_task_store.get_tasks_needing_reminder()

            for task in candidates:
                try:
                    stage = determine_reminder_stage(task, now)
                    if stage is None:
                        continue

                    if not is_cooldown_elapsed(task, now, config.REMINDER_COOLDOWN_MINUTES):
                        continue

                    # Генерируем текст через LLM (синхронный вызов в потоке)
                    text = await asyncio.to_thread(_generate_reminder_text, task, stage)

                    # Отправляем в группу
                    await _send_reminder(bot, task, text)

                    # Обновляем трекинг
                    task.last_reminder_at = now
                    task.reminder_stage = stage.value

                    logger.info(f"Напоминание отправлено: task={task.task_id}, stage={stage.value}, title={task.title[:30]}")

                except Exception as e:
                    logger.error(f"Ошибка напоминания для задачи {task.task_id}: {e}")

        except asyncio.CancelledError:
            logger.info("Reminder loop остановлен")
            break
        except Exception as e:
            logger.error(f"Ошибка в reminder loop: {e}")
