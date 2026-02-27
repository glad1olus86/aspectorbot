"""Обработчики команд бота."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.messages import get_help_message, get_start_message_group, get_start_message_private

router = Router(name="commands")


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """
    Обработчик команды /start.

    В личном чате отправляет полное приветствие.
    В группе отправляет краткое сообщение.
    """
    # Проверяем тип чата
    if message.chat.type == "private":
        text = get_start_message_private()
        await message.answer(text)
    else:
        # В группе отвечаем только если команда адресована боту
        # или если это личный вызов без упоминания
        text = get_start_message_group()
        await message.answer(text)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Обработчик команды /help."""
    text = get_help_message()
    await message.answer(text, parse_mode="Markdown")


__all__ = ["router"]
