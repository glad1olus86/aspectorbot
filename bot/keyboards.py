"""Inline-клавиатуры для бота."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import config


def create_trello_confirm_keyboard(card_id: str) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру подтверждения задачи.

    Args:
        card_id: Короткий ID задачи в in-memory хранилище

    Returns:
        InlineKeyboardMarkup с кнопками действий
    """
    row1 = [
        InlineKeyboardButton(
            text="✅ В Trello",
            callback_data=f"trello_confirm:{card_id}",
        ),
    ]
    # Кнопка "В группу" только если GROUP_CHAT_ID настроен
    if config.GROUP_CHAT_ID:
        row1.append(
            InlineKeyboardButton(
                text="📤 В группу",
                callback_data=f"group_send:{card_id}",
            )
        )

    row2 = [
        InlineKeyboardButton(
            text="📨 Отправить в ЛС",
            callback_data=f"forward_start:{card_id}",
        ),
        InlineKeyboardButton(
            text="✏️ Редактировать",
            callback_data=f"trello_edit:{card_id}",
        ),
    ]

    row3 = [
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data=f"trello_card_cancel:{card_id}",
        ),
    ]

    return InlineKeyboardMarkup(inline_keyboard=[row1, row2, row3])


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


def create_group_take_keyboard(task_id: str) -> InlineKeyboardMarkup:
    """Клавиатура "Взять в работу" для сообщения в группе."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🙋 Взять в работу",
                    callback_data=f"group_take:{task_id}",
                )
            ]
        ]
    )


def create_group_done_keyboard(task_id: str) -> InlineKeyboardMarkup:
    """Клавиатура "Задача выполнена" для сообщения в группе."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Задача выполнена",
                    callback_data=f"group_done:{task_id}",
                )
            ]
        ]
    )


__all__ = [
    "create_empty_keyboard",
    "create_trello_confirm_keyboard",
    "create_trello_edit_cancel_keyboard",
    "create_retry_keyboard",
    "create_group_take_keyboard",
    "create_group_done_keyboard",
]
