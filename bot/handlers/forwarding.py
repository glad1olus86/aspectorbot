"""Обработчики для пересылки задач в ЛС контактам."""

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from loguru import logger

from bot.handlers.trello import _pending_cards
from bot.messages import get_trello_card_message
from storage.contacts import contacts_store
from storage.users import user_registry

router = Router(name="forwarding")


def _build_forwarding_keyboard(owner_id: int, card_id: str, page: int = 0) -> InlineKeyboardMarkup:
    """Построить клавиатуру выбора контакта для отправки задачи."""
    contacts = contacts_store.get_contacts(owner_id)
    per_page = 5
    total_pages = max(1, (len(contacts) + per_page - 1) // per_page)
    
    if page < 0:
        page = 0
    elif page >= total_pages:
        page = total_pages - 1
        
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_contacts = contacts[start_idx:end_idx]
    
    buttons = []
    
    for contact in page_contacts:
        buttons.append([
            InlineKeyboardButton(
                text=f"👤 {contact.name}",
                callback_data=f"forward_send:{contact.id}:{card_id}"
            )
        ])
        
    pagination = []
    if page > 0:
        pagination.append(InlineKeyboardButton(text="⬅️", callback_data=f"forward_page:{page - 1}:{card_id}"))
    if total_pages > 1:
        pagination.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="ignore"))
    if page < total_pages - 1:
        pagination.append(InlineKeyboardButton(text="➡️", callback_data=f"forward_page:{page + 1}:{card_id}"))
        
    if pagination:
        buttons.append(pagination)
        
    buttons.append([
        InlineKeyboardButton(
            text="🔙 Назад к задаче",
            callback_data=f"forward_cancel:{card_id}"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data.startswith("forward_start:"))
async def forward_start_callback(callback: CallbackQuery) -> None:
    """Нажатие кнопки 'Отправить в ЛС' — показ списка контактов."""
    user_id = callback.from_user.id
    card_id = callback.data.split(":")[1]
    
    contacts = contacts_store.get_contacts(user_id)
    if not contacts:
        await callback.answer("У вас нет сохраненных контактов. Добавьте их через команду /contacts", show_alert=True)
        return
        
    keyboard = _build_forwarding_keyboard(user_id, card_id, 0)
    await callback.message.edit_text(
        "📨 <b>Отправка задачи в ЛС</b>\n\nВыберите кому отправить эту задачу:",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.startswith("forward_page:"))
async def forward_page_callback(callback: CallbackQuery) -> None:
    """Пагинация при выборе контакта для отправки."""
    user_id = callback.from_user.id
    parts = callback.data.split(":")
    page = int(parts[1])
    card_id = parts[2]
    
    keyboard = _build_forwarding_keyboard(user_id, card_id, page)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("forward_cancel:"))
async def forward_cancel_callback(callback: CallbackQuery) -> None:
    """Возврат назад к просмотру задачи."""
    card_id = callback.data.split(":")[1]
    card_data = _pending_cards.get(card_id)
    
    if not card_data:
        await callback.answer("❌ Данные задачи устарели", show_alert=True)
        return
        
    from bot.keyboards import create_trello_confirm_keyboard
    await callback.message.edit_text(
        get_trello_card_message(card_data["title"], card_data["description"], card_data.get("deadline"), card_data.get("assignee")),
        reply_markup=create_trello_confirm_keyboard(card_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("forward_send:"))
async def forward_send_callback(callback: CallbackQuery) -> None:
    """Отправка задачи выбранному контакту."""
    user_id = callback.from_user.id
    parts = callback.data.split(":")
    contact_id = parts[1]
    card_id = parts[2]
    
    card_data = _pending_cards.get(card_id)
    if not card_data:
        await callback.answer("❌ Данные задачи устарели.", show_alert=True)
        # Возвращаем пустое меню, так как задача уже исчезла
        from bot.keyboards import create_empty_keyboard
        await callback.message.edit_reply_markup(reply_markup=create_empty_keyboard())
        return
        
    contact = contacts_store.get_contact(user_id, contact_id)
    if not contact:
        await callback.answer("❌ Контакт не найден.", show_alert=True)
        return
        
    target_chat_id = user_registry.get_chat_id(contact.username)
    if not target_chat_id:
        await callback.answer(
            f"❌ Пользователь @{contact.username} не найден в базе бота.\n\n"
            "Попросите его найти бота и нажать /start, после чего вы сможете отправлять ему в ЛС.",
            show_alert=True
        )
        return
        
    sender_name = callback.from_user.first_name
    if callback.from_user.username:
        sender_name += f" (@{callback.from_user.username})"
        
    message_text = (
        f"📨 <b>Вам новая задача от {sender_name}!</b>\n\n"
        f"📋 <b>Задача:</b>\n\n"
        f"<b>Тема:</b> {card_data['title']}\n\n"
        f"<b>Описание:</b>\n{card_data['description']}"
    )
    
    photos = card_data.get("photo_file_ids", [])
    
    try:
        # Если есть фото, отправляем их с подписью
        if photos:
            if len(photos) == 1:
                await callback.bot.send_photo(
                    chat_id=target_chat_id, 
                    photo=photos[0], 
                    caption=message_text
                )
            else:
                media_group = [InputMediaPhoto(media=photos[0], caption=message_text)]
                for photo_id in photos[1:]:
                    media_group.append(InputMediaPhoto(media=photo_id))
                await callback.bot.send_media_group(chat_id=target_chat_id, media=media_group)
        else:
            # Иначе просто текстовое сообщение
            await callback.bot.send_message(chat_id=target_chat_id, text=message_text)
        
        # Увеличиваем статистику
        contacts_store.increment_stats(user_id, contact_id)
        
        # Удаляем задачу у отправителя так же, как мы это делаем при успешном Trello
        _pending_cards.pop(card_id, None)
        
        from bot.keyboards import create_empty_keyboard
        await callback.message.edit_text(
            f"✅ Задача успешно отправлена контакту {contact.name} (@{contact.username}) в ЛС.",
            reply_markup=create_empty_keyboard()
        )
        await callback.answer("Отправлено!")
        
    except Exception as e:
        logger.error(f"Не удалось отправить задачу в ЛС: {e}")
        await callback.answer(
            "❌ Ошибка отправки. Возможно контакт заблокировал бота.",
            show_alert=True
        )


__all__ = ["router"]
