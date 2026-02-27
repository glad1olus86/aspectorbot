"""Обработчик фотографий для привязки к карточкам Trello."""

from aiogram import F, Router
from aiogram.types import Message
from loguru import logger

from storage.user_photos import user_photo_store

router = Router(name="photos")


@router.message(F.photo)
async def handle_photo(message: Message) -> None:
    """
    Обработчик входящих фотографий.

    Сохраняет file_id самого большого размера в UserPhotoStore.
    Фото будет автоматически привязано к карточке Trello,
    если голосовое сообщение получено в течение 3 минут.
    """
    if not message.from_user:
        return

    # Telegram отправляет фото в нескольких размерах, последний — самый большой
    largest_photo = message.photo[-1]

    user_photo_store.add(
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        file_id=largest_photo.file_id,
    )

    logger.debug(
        f"Фото сохранено: chat={message.chat.id}, user={message.from_user.id}, "
        f"size={largest_photo.width}x{largest_photo.height}"
    )


__all__ = ["router"]
