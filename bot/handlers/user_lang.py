"""Обработчик команды /lang — выбор языка распознавания."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from loguru import logger

from config import config
from storage.user_lang import user_lang_store

router = Router(name="user_lang")


def _build_lang_keyboard(current_lang: str | None) -> InlineKeyboardMarkup:
    """Построить клавиатуру выбора языка с отметкой текущего."""
    languages = config.SUPPORTED_LANGUAGES
    flags = config.LANGUAGE_FLAGS

    buttons = []
    row = []

    for lang_code, lang_name in languages.items():
        flag = flags.get(lang_code, "")
        mark = " ✓" if lang_code == current_lang else ""
        row.append(
            InlineKeyboardButton(
                text=f"{flag} {lang_name}{mark}",
                callback_data=f"user_lang:{lang_code}",
            )
        )
        if len(row) == 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    # Кнопка сброса
    mark = " ✓" if current_lang is None else ""
    buttons.append([
        InlineKeyboardButton(
            text=f"🔄 Авто{mark}",
            callback_data="user_lang:reset",
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("lang"))
async def cmd_lang(message: Message) -> None:
    """Обработчик команды /lang — показать выбор языка (видит только отправитель)."""
    user_id = message.from_user.id
    current = user_lang_store.get(user_id)

    if current:
        lang_name = config.SUPPORTED_LANGUAGES.get(current, current)
        flag = config.LANGUAGE_FLAGS.get(current, "")
        status = f"Текущий язык: {flag} {lang_name}"
    else:
        status = "Текущий режим: 🔄 Автоопределение"

    text = (
        f"🌍 <b>Выбор языка распознавания</b>\n\n"
        f"{status}\n\n"
        f"Выберите язык для своих голосовых сообщений:"
    )
    keyboard = _build_lang_keyboard(current)

    is_group = message.chat.type in ("group", "supergroup")

    if is_group:
        # В группе: удаляем сообщение с командой, отправляем настройки в личку
        try:
            await message.delete()
        except Exception as e:
            logger.debug(f"Не удалось удалить команду /lang: {e}")

        try:
            await message.bot.send_message(
                chat_id=user_id,
                text=text,
                reply_markup=keyboard,
            )
        except Exception as e:
            # Если юзер не запускал бота в личке, отправить не получится
            logger.warning(f"Не удалось отправить настройки в личку юзеру {user_id}: {e}")
            # Отправляем короткое сообщение в группу
            hint = await message.answer(
                f"🔒 @{message.from_user.username or message.from_user.first_name}, "
                f"напишите мне в личку /start, чтобы я мог отправлять вам настройки."
            )
            # Автоудаление подсказки через 10 секунд
            import asyncio
            await asyncio.sleep(10)
            try:
                await hint.delete()
            except Exception:
                pass
    else:
        # В личке: просто отправляем настройки
        await message.answer(
            text,
            reply_markup=keyboard,
        )


@router.callback_query(F.data.startswith("user_lang:"))
async def handle_user_lang_select(callback: CallbackQuery) -> None:
    """Обработчик выбора языка через inline-кнопку."""
    user_id = callback.from_user.id
    value = callback.data.split(":", 1)[1]

    if value == "reset":
        user_lang_store.reset(user_id)
        await callback.message.edit_text(
            "🌍 <b>Выбор языка распознавания</b>\n\n"
            "✅ Язык сброшен — теперь бот будет определять язык автоматически.",
            reply_markup=_build_lang_keyboard(None),
        )
        await callback.answer("Автоопределение включено")
    elif value in config.SUPPORTED_LANGUAGES:
        user_lang_store.set(user_id, value)
        lang_name = config.SUPPORTED_LANGUAGES[value]
        flag = config.LANGUAGE_FLAGS.get(value, "")
        await callback.message.edit_text(
            f"🌍 <b>Выбор языка распознавания</b>\n\n"
            f"✅ Язык установлен: {flag} {lang_name}\n"
            f"Все ваши голосовые будут распознаваться на этом языке.",
            reply_markup=_build_lang_keyboard(value),
        )
        await callback.answer(f"Выбран: {flag} {lang_name}")
    else:
        await callback.answer("❌ Неизвестный язык", show_alert=True)


__all__ = ["router"]
