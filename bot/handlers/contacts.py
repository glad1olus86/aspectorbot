"""Обработчик команды /contacts — список контактов пользователя."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from loguru import logger

from storage.contacts import contacts_store

router = Router(name="contacts")


class ContactState(StatesGroup):
    waiting_for_name = State()
    waiting_for_username = State()
    waiting_for_triggers = State()


def _build_contacts_keyboard(owner_id: int, page: int = 0) -> InlineKeyboardMarkup:
    """Построить клавиатуру со списком контактов."""
    contacts = contacts_store.get_contacts(owner_id)
    per_page = 5
    total_pages = max(1, (len(contacts) + per_page - 1) // per_page)
    
    # Защита от выхода за пределы
    if page < 0:
        page = 0
    elif page >= total_pages:
        page = total_pages - 1
        
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_contacts = contacts[start_idx:end_idx]
    
    buttons = []
    
    # Кнопки контактов (по одному в строке, чтобы влезло имя)
    for contact in page_contacts:
        buttons.append([
            InlineKeyboardButton(
                text=f"👤 {contact.name}",
                callback_data=f"contact_view:{contact.id}"
            )
        ])
        
    # Кнопки пагинации
    pagination = []
    if page > 0:
        pagination.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"contacts_page:{page - 1}"))
    if total_pages > 1:
        pagination.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="ignore"))
    if page < total_pages - 1:
        pagination.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"contacts_page:{page + 1}"))
        
    if pagination:
        buttons.append(pagination)
        
    # Кнопка добавления
    buttons.append([
        InlineKeyboardButton(
            text="➕ Добавить контакт",
            callback_data="contact_add"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("contacts"))
async def cmd_contacts(message: Message, state: FSMContext) -> None:
    """Обработчик команды /contacts."""
    await state.clear()
    
    user_id = message.from_user.id
    is_group = message.chat.type in ("group", "supergroup")
    
    text = "🗓 <b>Ваши контакты</b>\n\nЗдесь вы можете управлять списком людей, которым можно отправлять задачи."
    keyboard = _build_contacts_keyboard(user_id, 0)
    
    if is_group:
        try:
            await message.delete()
        except Exception:
            pass
            
        try:
            await message.bot.send_message(
                chat_id=user_id,
                text=text,
                reply_markup=keyboard,
            )
        except Exception:
            hint = await message.answer(
                f"🔒 @{message.from_user.username or message.from_user.first_name}, "
                f"напишите мне в личку /start, чтобы открыть ваши контакты."
            )
            import asyncio
            await asyncio.sleep(10)
            try:
                await hint.delete()
            except Exception:
                pass
    else:
        await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("contacts_page:"))
async def contacts_page_callback(callback: CallbackQuery) -> None:
    """Перелистывание страниц контактов (и возврат из профиля)."""
    user_id = callback.from_user.id
    page = int(callback.data.split(":")[1])
    
    text = "🗓 <b>Ваши контакты</b>\n\nЗдесь вы можете управлять списком людей, которым можно отправлять задачи."
    keyboard = _build_contacts_keyboard(user_id, page)
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("contact_view:"))
async def contact_view_callback(callback: CallbackQuery) -> None:
    """Просмотр профиля контакта."""
    user_id = callback.from_user.id
    contact_id = callback.data.split(":")[1]
    
    contact = contacts_store.get_contact(user_id, contact_id)
    if not contact:
        await callback.answer("❌ Контакт не найден", show_alert=True)
        return
        
    triggers_line = ", ".join(contact.trigger_words) if contact.trigger_words else "—"
    text = (
        f"👤 <b>Профиль контакта</b>\n\n"
        f"<b>Имя:</b> {contact.name}\n"
        f"<b>Username:</b> @{contact.username}\n"
        f"<b>Триггер-слова:</b> {triggers_line}\n"
        f"<b>Задач отправлено:</b> {contact.tasks_sent}\n"
    )
    
    buttons = [
        [
            InlineKeyboardButton(text="🔙 К списку контактов", callback_data="contacts_page:0")
        ]
    ]
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()


# === Добавление контакта (FSM) ===

@router.callback_query(F.data == "contact_add")
async def contact_add_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Кнопка добавления контакта."""
    await state.set_state(ContactState.waiting_for_name)
    
    # Сохраняем ID сообщения, чтобы его потом редактировать/удалять
    await state.update_data(menu_message_id=callback.message.message_id)
    
    buttons = [[InlineKeyboardButton(text="❌ Отмена", callback_data="contact_cancel")]]
    
    await callback.message.edit_text(
        "➕ <b>Добавление контакта</b>\n\nВведите понятное вам имя человека (например: Иван Разработчик):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()


@router.callback_query(F.data == "contact_cancel")
async def contact_cancel_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Отмена добавления контакта."""
    await state.clear()
    user_id = callback.from_user.id
    
    text = "🗓 <b>Ваши контакты</b>\n\nЗдесь вы можете управлять списком людей, которым можно отправлять задачи."
    keyboard = _build_contacts_keyboard(user_id, 0)
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.message(ContactState.waiting_for_name)
async def process_contact_name(message: Message, state: FSMContext) -> None:
    """Обработка ввода имени контакта."""
    name = message.text.strip()
    if len(name) < 2 or len(name) > 50:
        await message.answer("⚠️ Имя должно быть от 2 до 50 символов. Попробуйте снова:")
        return
        
    await state.update_data(contact_name=name)
    await state.set_state(ContactState.waiting_for_username)
    
    # Удаляем сообщение с введенным именем, чтобы не засорять чат (если получится)
    try:
        await message.delete()
    except Exception:
        pass
        
    data = await state.get_data()
    menu_message_id = data.get("menu_message_id")
    
    text = (
        f"➕ <b>Добавление контакта</b>\n"
        f"Имя: {name}\n\n"
        f"Теперь введите Telegram Username (начинается с @) этого человека:"
    )
    buttons = [[InlineKeyboardButton(text="❌ Отмена", callback_data="contact_cancel")]]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    if menu_message_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=menu_message_id,
                text=text,
                reply_markup=keyboard
            )
        except Exception:
            msg = await message.answer(text, reply_markup=keyboard)
            await state.update_data(menu_message_id=msg.message_id)
    else:
        msg = await message.answer(text, reply_markup=keyboard)
        await state.update_data(menu_message_id=msg.message_id)


@router.message(ContactState.waiting_for_username)
async def process_contact_username(message: Message, state: FSMContext) -> None:
    """Обработка ввода юзернейма — переход к триггер-словам."""
    username = message.text.strip()

    # Базовая валидация юзернейма
    if not username.startswith("@") and " " in username:
        await message.answer("⚠️ Введите корректный Telegram Username (например: @ivan_dev). Попробуйте снова:")
        return

    await state.update_data(contact_username=username)
    await state.set_state(ContactState.waiting_for_triggers)

    try:
        await message.delete()
    except Exception:
        pass

    data = await state.get_data()
    name = data.get("contact_name")
    menu_message_id = data.get("menu_message_id")

    text = (
        f"➕ <b>Добавление контакта</b>\n"
        f"Имя: {name}\n"
        f"Username: {username}\n\n"
        f"Введите <b>триггер-слова</b> через запятую — по ним бот будет определять, "
        f"что задача предназначена этому человеку.\n\n"
        f"Пример: <code>вася, василий, васька</code>\n\n"
        f"Или отправьте <code>-</code> чтобы пропустить."
    )
    buttons = [[InlineKeyboardButton(text="❌ Отмена", callback_data="contact_cancel")]]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    if menu_message_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=menu_message_id,
                text=text,
                reply_markup=keyboard,
            )
        except Exception:
            msg = await message.answer(text, reply_markup=keyboard)
            await state.update_data(menu_message_id=msg.message_id)
    else:
        msg = await message.answer(text, reply_markup=keyboard)
        await state.update_data(menu_message_id=msg.message_id)


@router.message(ContactState.waiting_for_triggers)
async def process_contact_triggers(message: Message, state: FSMContext) -> None:
    """Обработка триггер-слов и сохранение контакта."""
    raw = message.text.strip()

    # Парсим триггер-слова
    if raw == "-":
        trigger_words = []
    else:
        trigger_words = [w.strip() for w in raw.split(",") if w.strip()]

    data = await state.get_data()
    name = data.get("contact_name")
    username = data.get("contact_username")
    user_id = message.from_user.id

    contacts_store.add_contact(user_id, name, username, trigger_words)
    await state.clear()

    try:
        await message.delete()
    except Exception:
        pass

    menu_message_id = data.get("menu_message_id")
    text = "🗓 <b>Ваши контакты</b>\n\n✅ Контакт успешно добавлен."
    keyboard = _build_contacts_keyboard(user_id, 0)

    if menu_message_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=menu_message_id,
                text=text,
                reply_markup=keyboard
            )
        except Exception:
            await message.answer(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)


__all__ = ["router"]
