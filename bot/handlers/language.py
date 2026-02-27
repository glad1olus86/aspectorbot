"""Обработчик выбора языка."""

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery

from bot.keyboards import create_empty_keyboard
from bot.messages import get_language_selected_message
from loguru import logger
from task_queue.manager import QueueManager
from task_queue.task import TaskStatus
from storage.pending import pending_store

router = Router(name="language")


@router.callback_query(F.data.startswith("lang_select:"))
async def handle_language_select(callback: CallbackQuery, queue_manager: QueueManager) -> None:
    """
    Обработчик выбора языка из inline-клавиатуры.

    Формат callback_data: lang_select:{task_id}:{lang_code}

    1. Парсит task_id и lang_code
    2. Пытается зарезервировать задачу (claim)
    3. Если успешно — обновляет сообщение и кладёт задачу в очередь
    4. Если нет — тихий ответ что уже выбрано
    """
    # Парсим callback_data
    parts = callback.data.split(":")
    if len(parts) != 3:
        logger.error(f"Некорректный callback_data: {callback.data}")
        await callback.answer("⚡ Ошибка формата запроса", show_alert=False)
        return

    task_id = parts[1]
    lang_code = parts[2]

    # Получаем username пользователя
    username = callback.from_user.username

    logger.info(
        f"Выбор языка: task_id={task_id}, lang={lang_code}, user={username}"
    )

    # Пытаемся зарезервировать задачу
    if not pending_store.claim(task_id, username):
        # Задача уже зарезервирована другим пользователем
        await callback.answer(
            "⚡ Язык уже выбран другим участником, обработка идёт!",
            show_alert=False,
        )
        return

    # Получаем задачу из хранилища
    task = pending_store.resolve(task_id, lang_code)
    if task is None:
        logger.error(f"Задача {task_id} не найдена в PendingStore")
        await callback.answer(
            "⚡ Задача не найдена. Попробуйте отправить голосовое ещё раз.",
            show_alert=False,
        )
        return

    # Обновляем сообщение с кнопками (убираем кнопки)
    try:
        await callback.message.edit_reply_markup(
            reply_markup=create_empty_keyboard()
        )
    except TelegramBadRequest as e:
        # Сообщение могло быть удалено или изменено
        logger.warning(f"Не удалось отредактировать сообщение с кнопками: {e}")

    # Отправляем подтверждение
    confirm_text = get_language_selected_message(username)
    try:
        await callback.message.edit_text(
            text=confirm_text,
            reply_markup=create_empty_keyboard(),
        )
    except TelegramBadRequest as e:
        logger.warning(f"Не удалось отредактировать текст сообщения: {e}")

    await callback.answer("Принято! Начинаю обработку...", show_alert=False)

    # Обновляем задачу и кладём обратно в очередь
    task.set_status(TaskStatus.QUEUED)
    await queue_manager.add_task(task)

    logger.info(f"Задача {task_id} с языком {lang_code} добавлена в очередь")


__all__ = ["router"]
