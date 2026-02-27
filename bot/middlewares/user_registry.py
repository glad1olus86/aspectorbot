from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

from storage.users import user_registry


class UserRegistryMiddleware(BaseMiddleware):
    """
    Middleware для автоматической регистрации (обновления) связи username -> chat_id.
    """
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        
        user = None
        chat = None
        
        if isinstance(event, Message):
            user = event.from_user
            chat = event.chat
        elif isinstance(event, CallbackQuery):
            user = event.from_user
            if event.message:
                chat = event.message.chat
                
        if user and chat and chat.type == "private" and user.username:
            # Регистрируем только личные чаты, чтобы знать куда писать в ЛС
            user_registry.register(user.username, chat.id)
            
        return await handler(event, data)
