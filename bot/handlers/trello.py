"""Обработчики для интеграции с Trello и Gemini (задачи)."""

import uuid

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, Voice, Audio
from loguru import logger

from bot.keyboards import (
    create_empty_keyboard,
    create_trello_confirm_keyboard,
    create_trello_edit_cancel_keyboard,
)
from bot.messages import (
    get_trello_card_message,
    get_trello_created_message,
    get_trello_edit_prompt_message,
    get_trello_error_message,
    get_trello_generating_message,
)
from utils.trello_client import trello_client
from utils.trello_gemini import edit_trello_card, generate_trello_card

router = Router(name="trello")

# In-memory хранилища
_pending_cards: dict[str, dict] = {}  # {card_id: {"title": ..., "description": ..., "photo_file_ids": [...]}}
_failed_tasks: dict[str, dict] = {}   # {failed_id: {"text": ..., "photo_file_ids": [...], "action": ..., "action_data": ...}}


class TrelloState(StatesGroup):
    """Состояния для процесса создания карточки Trello."""

    waiting_for_edits = State()  # Ожидание правок от пользователя





def _store_card(card_data: dict) -> str:
    """Сохранить данные карточки и вернуть короткий ID."""
    card_id = uuid.uuid4().hex[:8]
    _pending_cards[card_id] = card_data
    return card_id


def store_failed_task(task_data: dict) -> str:
    """Сохранить данные провалившейся генерации задачи для повтора."""
    failed_id = uuid.uuid4().hex[:8]
    _failed_tasks[failed_id] = task_data
    return failed_id


def _get_card(card_id: str) -> dict | None:
    """Получить данные карточки по ID."""
    return _pending_cards.get(card_id)


def _pop_card(card_id: str) -> dict | None:
    """Извлечь данные карточки по ID (удаляет из хранилища)."""
    return _pending_cards.pop(card_id, None)


# === Обработчики отмены ===


@router.callback_query(F.data.startswith("trello_card_cancel:"))
async def trello_card_cancel_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик нажатия кнопки "❌ Отмена" на этапе подтверждения/редактирования задачи.

    Очищает pending card, FSM состояние и убирает inline-кнопки.
    """
    parts = callback.data.split(":", 1)
    if len(parts) < 2:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    card_id = parts[1]
    _pending_cards.pop(card_id, None)
    await state.clear()

    await callback.message.edit_reply_markup(reply_markup=create_empty_keyboard())
    await callback.answer()
    logger.info(f"Задача отменена: card_id={card_id}")


@router.callback_query(F.data.startswith("retry_gemini:"))
async def retry_gemini_callback(callback: CallbackQuery) -> None:
    """
    Повторная попытка сгенерировать карточку, если Gemini выдал ошибку.
    """
    failed_id = callback.data.split(":")[1]
    task_data = _failed_tasks.get(failed_id)
    
    if not task_data:
        await callback.answer("⏳ Данные устарели, запишите аудио заново.", show_alert=True)
        return

    # Убираем кнопку повтора
    await callback.message.edit_reply_markup(reply_markup=create_empty_keyboard())
    
    # Сообщение о генерации
    generating_msg = await callback.message.reply(get_trello_generating_message())
    
    import asyncio
    
    # В зависимости от типа действия
    if task_data.get("action") == "edit":
        card_id = task_data.get("action_data", {}).get("card_id")
        orig_card = _get_card(card_id) if card_id else None
        if not orig_card:
            await generating_msg.delete()
            await callback.answer("⏳ Исходная задача устарела.", show_alert=True)
            return
            
        card_data = await asyncio.to_thread(edit_trello_card, orig_card, task_data["text"])
        if card_data:
            # Восстанавливаем фото из сохраненных провалившихся данных
            card_data["photo_file_ids"] = task_data.get("photo_file_ids", [])
            _pending_cards[card_id] = card_data
            
            await generating_msg.delete()
            await callback.message.reply(
                get_trello_card_message(card_data["title"], card_data["description"]),
                reply_markup=create_trello_confirm_keyboard(card_id),
            )
            _failed_tasks.pop(failed_id, None)
            await callback.answer("Успешно!")
        else:
            from bot.keyboards import create_retry_keyboard
            await generating_msg.delete()
            await callback.message.reply(
                get_trello_error_message(),
                reply_markup=create_retry_keyboard(failed_id)
            )
            await callback.answer("Снова ошибка Gemini")
    else:
        # Стандартное создание
        card_data = await asyncio.to_thread(generate_trello_card, task_data["text"])
        
        await generating_msg.delete()
        if card_data:
            card_data["photo_file_ids"] = task_data.get("photo_file_ids", [])
            card_id = _store_card(card_data)
            
            await callback.message.reply(
                get_trello_card_message(card_data["title"], card_data["description"]),
                reply_markup=create_trello_confirm_keyboard(card_id),
            )
            _failed_tasks.pop(failed_id, None)
            await callback.answer("Успешно!")
        else:
            from bot.keyboards import create_retry_keyboard
            await callback.message.reply(
                get_trello_error_message(),
                reply_markup=create_retry_keyboard(failed_id)
            )
            await callback.answer("Снова ошибка Gemini")


# === Основные обработчики ===


@router.callback_query(F.data.startswith("trello_confirm:"))
async def trello_confirm_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик нажатия кнопки "✅ В Trello".

    Создаёт карточку в Trello и загружает фотографии как вложения.
    """
    logger.info(f"=== trello_confirm_callback: callback_data={callback.data}")

    # Парсим callback_data: trello_confirm:card_id
    parts = callback.data.split(":", 1)
    if len(parts) < 2:
        logger.error(f"Некорректный callback_data: {callback.data}")
        return

    card_id = parts[1]
    card_data = _pop_card(card_id)

    if not card_data or "title" not in card_data:
        logger.error(f"Карточка не найдена или некорректна: card_id={card_id}")
        await callback.answer("❌ Данные карточки не найдены. Попробуйте заново.", show_alert=True)
        return

    logger.info(f"Создание карточки в Trello: {card_data['title']}")

    # Очищаем состояние
    await state.clear()

    # Создаём карточку в Trello
    logger.info("Вызов trello_client.create_card...")
    result = await trello_client.create_card(
        title=card_data["title"],
        description=card_data["description"],
    )
    logger.info(f"Trello вернул: {result}")

    if not result:
        logger.error("Trello вернул None, отправляем ошибку")
        await callback.message.answer(get_trello_error_message())
        await callback.answer()
        return

    # Загружаем фотографии как вложения
    photo_file_ids = card_data.get("photo_file_ids", [])
    attached_count = 0

    if photo_file_ids and result.get("id"):
        trello_card_id = result["id"]
        bot = callback.bot

        for i, file_id in enumerate(photo_file_ids):
            try:
                file = await bot.get_file(file_id)
                photo_bytes = await bot.download_file(file.file_path)
                success = await trello_client.add_attachment(
                    card_id=trello_card_id,
                    filename=f"photo_{i + 1}.jpg",
                    file_data=photo_bytes.read(),
                )
                if success:
                    attached_count += 1
            except Exception as e:
                logger.error(f"Ошибка загрузки фото {i + 1} в Trello: {e}")

        if attached_count:
            logger.info(f"Загружено {attached_count}/{len(photo_file_ids)} фото в карточку {trello_card_id}")

    # Убираем кнопки и отправляем сообщение об успехе
    await callback.message.edit_reply_markup(reply_markup=create_empty_keyboard())

    logger.info(f"Карточка создана: {result['url']}")
    await callback.message.answer(
        get_trello_created_message(result["url"], result["name"], photo_count=attached_count),
    )

    await callback.answer()


@router.callback_query(F.data.startswith("trello_edit:"))
async def trello_edit_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик нажатия кнопки "✏️ Редактировать".

    Запрашивает правки у пользователя.
    """
    # Парсим callback_data: trello_edit:card_id
    parts = callback.data.split(":", 1)
    if len(parts) < 2:
        logger.error(f"Некорректный callback_data: {callback.data}")
        return

    card_id = parts[1]

    if not _get_card(card_id):
        await callback.answer("❌ Данные карточки не найдены. Попробуйте заново.", show_alert=True)
        return

    # Сохраняем card_id в FSM состоянии
    await state.update_data(card_id=card_id)
    await state.set_state(TrelloState.waiting_for_edits)

    # Удаляем кнопки у сообщения с карточкой
    await callback.message.edit_reply_markup(reply_markup=create_empty_keyboard())

    # Отправляем сообщение с просьбой ввести правки (с кнопкой отмены)
    await callback.message.answer(
        get_trello_edit_prompt_message(),
        reply_markup=create_trello_edit_cancel_keyboard(card_id),
    )

    await callback.answer()


@router.message(TrelloState.waiting_for_edits, F.text)
async def trello_edits_message(message: Message, state: FSMContext) -> None:
    """
    Обработчик текста правок от пользователя.

    Отправляет на Gemini для редактирования карточки.
    """
    edits = message.text
    logger.info(f"Получены правки для карточки: {edits}")

    # Получаем card_id из состояния
    data = await state.get_data()
    card_id = data.get("card_id")

    if not card_id:
        logger.error("Нет card_id в состоянии")
        await message.answer(get_trello_error_message())
        await state.clear()
        return

    original_card_data = _get_card(card_id)

    if not original_card_data:
        logger.error(f"Карточка не найдена: card_id={card_id}")
        await message.answer(get_trello_error_message())
        await state.clear()
        return

    # Отправляем сообщение о генерации
    generating_msg = await message.answer(get_trello_generating_message())

    # Редактируем карточку через Gemini
    edited_card_data = edit_trello_card(original_card_data, edits)

    # Удаляем сообщение о генерации
    await generating_msg.delete()

    if not edited_card_data:
        await message.answer(get_trello_error_message())
        await state.clear()
        return

    # Сохраняем photo_file_ids из оригинальной карточки
    edited_card_data["photo_file_ids"] = original_card_data.get("photo_file_ids", [])

    # Обновляем данные карточки в хранилище
    _pending_cards[card_id] = edited_card_data

    # Отправляем обновлённую карточку на подтверждение
    await message.answer(
        get_trello_card_message(
            edited_card_data["title"],
            edited_card_data["description"],
        ),
        reply_markup=create_trello_confirm_keyboard(card_id),
    )

    # Остаёмся в состоянии ожидания (можно снова редактировать)


@router.message(TrelloState.waiting_for_edits, F.voice | F.audio)
async def trello_edits_voice(message: Message, state: FSMContext) -> None:
    """
    Обработчик голосовых правок от пользователя.

    Добавляет аудио в очередь распознавания с действием "edit".
    """
    logger.info("Получены голосовые правки для карточки")

    # Получаем card_id из состояния
    data = await state.get_data()
    card_id = data.get("card_id")

    if not card_id:
        logger.error("Нет card_id в состоянии")
        await message.answer(get_trello_error_message())
        await state.clear()
        return

    original_card_data = _get_card(card_id)

    if not original_card_data:
        logger.error(f"Карточка не найдена: card_id={card_id}")
        await message.answer(get_trello_error_message())
        await state.clear()
        return

    from task_queue.manager import get_queue_manager
    from task_queue.task import VoiceTask, TaskStatus
    from datetime import datetime
    import uuid
    from config import config

    qm = get_queue_manager()
    file_id = getattr(message, "voice", getattr(message, "audio", None)).file_id

    task = VoiceTask(
        task_id=str(uuid.uuid4()),
        chat_id=message.chat.id,
        message_id=message.message_id,
        file_id=file_id,
        status=TaskStatus.QUEUED,
        created_at=datetime.now(),
        user_id=message.from_user.id if message.from_user else None,
        username=message.from_user.username if message.from_user else None,
        action="edit",
        action_data={"card_id": card_id}
    )

    await qm.add_task(task)

    queue_size = qm.queue.qsize()
    if queue_size >= config.QUEUE_NOTIFY_THRESHOLD:
        from bot.messages import get_queue_message
        await message.answer(get_queue_message(queue_size), reply_to_message_id=message.message_id)
    else:
        await message.answer("🎤 Голосовые правки приняты. Распознаю аудио и обновляю задачу...")

    # Остаёмся в состоянии ожидания


__all__ = ["router", "TrelloState", "_store_card", "store_failed_task"]
