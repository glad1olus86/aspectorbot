"""Обработчики отправки задач в группу разработчиков."""

import uuid

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from loguru import logger

from bot.keyboards import (
    create_empty_keyboard,
    create_group_done_keyboard,
    create_group_take_keyboard,
)
from bot.messages import (
    get_group_task_done_message,
    get_group_task_in_progress_message,
    get_group_task_pending_message,
    get_task_completed_dm_message,
)
from config import config
from storage.group_tasks import GroupTask, GroupTaskStatus, group_task_store

router = Router(name="group_tasks")


def _build_message_link(chat_id: int, message_id: int) -> str:
    """Построить ссылку на сообщение в группе/супергруппе."""
    chat_id_str = str(chat_id)
    if chat_id_str.startswith("-100"):
        short_id = chat_id_str[4:]
    else:
        short_id = chat_id_str.lstrip("-")
    return f"https://t.me/c/{short_id}/{message_id}"


# ─── Отправка в группу ──────────────────────────────────────────────────


@router.callback_query(F.data.startswith("group_send:"))
async def group_send_callback(callback: CallbackQuery) -> None:
    """
    Отправить карточку в группу разработчиков.

    Callback data: group_send:{card_id}
    """
    card_id = callback.data.split(":", 1)[1]

    from bot.handlers.trello import _pop_card
    card_data = _pop_card(card_id)

    if not card_data or "title" not in card_data:
        await callback.answer("❌ Данные карточки не найдены.", show_alert=True)
        return

    if not config.GROUP_CHAT_ID:
        await callback.answer("❌ GROUP_CHAT_ID не настроен.", show_alert=True)
        return

    # Дедлайн и исполнитель из LLM (могут быть None)
    deadline = card_data.get("deadline")
    assignee = card_data.get("assignee")

    # Создаём GroupTask
    task_id = uuid.uuid4().hex[:8]
    task = GroupTask(
        task_id=task_id,
        title=card_data["title"],
        description=card_data["description"],
        creator_user_id=callback.from_user.id,
        creator_username=callback.from_user.username,
        deadline=deadline,
        photo_file_ids=card_data.get("photo_file_ids", []),
    )

    # Отправляем в группу
    text = get_group_task_pending_message(
        title=task.title,
        description=task.description,
        creator_username=task.creator_username,
        deadline=task.deadline,
        assignee=assignee,
    )
    keyboard = create_group_take_keyboard(task_id)

    try:
        msg = await callback.bot.send_message(
            chat_id=config.GROUP_CHAT_ID,
            text=text,
            reply_markup=keyboard,
        )
        task.group_message_id = msg.message_id
    except TelegramBadRequest as e:
        logger.error(f"Не удалось отправить задачу в группу: {e}")
        await callback.answer("❌ Не удалось отправить в группу.", show_alert=True)
        return

    group_task_store.store(task)

    await callback.message.edit_reply_markup(reply_markup=create_empty_keyboard())
    await callback.answer("📤 Задача отправлена в группу!")
    logger.info(f"Задача {task_id} отправлена в группу {config.GROUP_CHAT_ID}, дедлайн={deadline}")


# ─── Взять в работу ─────────────────────────────────────────────────────


@router.callback_query(F.data.startswith("group_take:"))
async def group_take_callback(callback: CallbackQuery) -> None:
    """
    Взять задачу в работу.

    Callback data: group_take:{task_id}
    """
    task_id = callback.data.split(":", 1)[1]
    task = group_task_store.get(task_id)

    if not task:
        await callback.answer("❌ Задача не найдена.", show_alert=True)
        return

    if task.status != GroupTaskStatus.PENDING:
        await callback.answer("⚡ Задача уже взята в работу!", show_alert=False)
        return

    success = group_task_store.take(
        task_id=task_id,
        user_id=callback.from_user.id,
        username=callback.from_user.username,
    )

    if not success:
        await callback.answer("⚡ Задача уже взята в работу!", show_alert=False)
        return

    # Обновляем сообщение в группе
    deadline_str = task.deadline or "Не указан"
    text = get_group_task_in_progress_message(
        title=task.title,
        description=task.description,
        creator_username=task.creator_username,
        worker_username=task.worker_username,
        deadline_str=deadline_str,
    )
    keyboard = create_group_done_keyboard(task_id)

    try:
        await callback.message.edit_text(text=text, reply_markup=keyboard)
    except TelegramBadRequest as e:
        logger.error(f"Не удалось обновить сообщение задачи: {e}")

    await callback.answer(f"🔵 Вы взяли задачу в работу!")
    logger.info(f"Задача {task_id} взята @{callback.from_user.username}, дедлайн={deadline_str}")


# ─── Задача выполнена ────────────────────────────────────────────────────


@router.callback_query(F.data.startswith("group_done:"))
async def group_done_callback(callback: CallbackQuery) -> None:
    """
    Отметить задачу как выполненную.

    Callback data: group_done:{task_id}
    """
    task_id = callback.data.split(":", 1)[1]
    task = group_task_store.get(task_id)

    if not task:
        await callback.answer("❌ Задача не найдена.", show_alert=True)
        return

    if task.status != GroupTaskStatus.IN_PROGRESS:
        await callback.answer("⚡ Задача не в статусе «В работе».", show_alert=False)
        return

    # Только исполнитель может завершить
    if callback.from_user.id != task.worker_user_id:
        await callback.answer("❌ Только исполнитель может завершить задачу.", show_alert=True)
        return

    success = group_task_store.complete(task_id)
    if not success:
        await callback.answer("❌ Ошибка при завершении задачи.", show_alert=True)
        return

    # Обновляем сообщение в группе
    completed_str = task.completed_at.strftime("%d.%m %H:%M")
    text = get_group_task_done_message(
        title=task.title,
        description=task.description,
        creator_username=task.creator_username,
        worker_username=task.worker_username,
        completed_str=completed_str,
    )

    try:
        await callback.message.edit_text(text=text, reply_markup=create_empty_keyboard())
    except TelegramBadRequest as e:
        logger.error(f"Не удалось обновить сообщение задачи: {e}")

    await callback.answer("✅ Задача выполнена!")

    # Отправляем уведомление автору в ЛС
    dm_text = get_task_completed_dm_message(
        title=task.title,
        worker_username=task.worker_username,
        completed_str=completed_str,
    )

    # Кнопка "Перейти к сообщению"
    link_keyboard = None
    if task.group_message_id and config.GROUP_CHAT_ID:
        link = _build_message_link(config.GROUP_CHAT_ID, task.group_message_id)
        link_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💬 Перейти к сообщению", url=link)]
            ]
        )

    try:
        await callback.bot.send_message(
            chat_id=task.creator_user_id,
            text=dm_text,
            reply_markup=link_keyboard,
        )
        logger.info(f"Уведомление о выполнении отправлено автору {task.creator_user_id}")
    except Exception as e:
        logger.warning(f"Не удалось отправить уведомление автору {task.creator_user_id}: {e}")

    logger.info(f"Задача {task_id} выполнена @{task.worker_username}")


__all__ = ["router"]
