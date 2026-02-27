"""Inline-клавиатуры для бота."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from loguru import logger

from config import config


def create_language_keyboard(task_id: str) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру выбора языка.

    Args:
        task_id: UUID задачи для callback_data

    Returns:
        InlineKeyboardMarkup с кнопками выбора языка
    """
    languages = config.SUPPORTED_LANGUAGES
    flags = config.LANGUAGE_FLAGS

    buttons = []
    row = []

    for lang_code, lang_name in languages.items():
        flag = flags.get(lang_code, "")
        callback_data = f"lang_select:{task_id}:{lang_code}"
        row.append(
            InlineKeyboardButton(
                text=f"{flag} {lang_name}",
                callback_data=callback_data,
            )
        )
        # После каждых 2 кнопок начинаем новый ряд
        if len(row) == 2:
            buttons.append(row)
            row = []

    # Добавляем оставшиеся кнопки
    if row:
        buttons.append(row)

    return InlineKeyboardMarkup(inline_keyboard=buttons)





def create_trello_confirm_keyboard(card_id: str) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру подтверждения задачи.

    Args:
        card_id: Короткий ID задачи в in-memory хранилище

    Returns:
        InlineKeyboardMarkup с кнопками "В Trello", "Отправить в ЛС", "Редактировать" и "Отмена"
    """
    buttons = [
        [
            InlineKeyboardButton(
                text="✅ В Trello",
                callback_data=f"trello_confirm:{card_id}",
            ),
            InlineKeyboardButton(
                text="📨 Отправить в ЛС",
                callback_data=f"forward_start:{card_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="✏️ Редактировать",
                callback_data=f"trello_edit:{card_id}",
            ),
            InlineKeyboardButton(
                text="❌ Отмена",
                callback_data=f"trello_card_cancel:{card_id}",
            ),
        ],
    ]

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_trello_edit_cancel_keyboard(card_id: str) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру с кнопкой отмены во время редактирования.

    Args:
        card_id: Короткий ID задачи в in-memory хранилище

    Returns:
        InlineKeyboardMarkup с кнопкой "❌ Отмена редактирования"
    """
    buttons = [
        [
            InlineKeyboardButton(
                text="❌ Отмена редактирования",
                callback_data=f"trello_card_cancel:{card_id}",
            ),
        ]
    ]

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_empty_keyboard() -> InlineKeyboardMarkup:
    """
    Создать пустую клавиатуру (для удаления кнопок).

    Returns:
        InlineKeyboardMarkup с пустой клавиатурой
    """
    return InlineKeyboardMarkup(inline_keyboard=[])


def create_retry_keyboard(failed_id: str) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру с кнопкой повтора после ошибки генерации.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Повторить генерацию",
                    callback_data=f"retry_gemini:{failed_id}"
                )
            ]
        ]
    )


__all__ = [
    "create_language_keyboard",
    "create_empty_keyboard",
    "create_trello_confirm_keyboard",
    "create_trello_edit_cancel_keyboard",
    "create_retry_keyboard",
]
