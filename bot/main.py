"""Точка входа для Aspector STT бота."""

import asyncio
import signal

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from loguru import logger

from bot.handlers.commands import router as commands_router
from bot.handlers.contacts import router as contacts_router
from bot.handlers.forwarding import router as forwarding_router
from bot.handlers.photos import router as photos_router
from bot.handlers.trello import router as trello_router
from bot.handlers.group_tasks import router as group_tasks_router
from bot.handlers.voice import router as voice_router
from config import config
from task_queue.manager import QueueManager
from bot.middlewares.user_registry import UserRegistryMiddleware
from utils.logger import setup_logger


async def on_startup(bot: Bot, queue_manager: QueueManager) -> None:
    """
    Выполняется при запуске бота.

    Args:
        bot: Экземпляр бота
        queue_manager: Менеджер очереди
    """
    logger.info("Бот запускается...")

    # Создаём необходимые директории
    config.BASE_DIR.mkdir(parents=True, exist_ok=True)
    config.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    config.TEMP_DIR.mkdir(parents=True, exist_ok=True)

    # Запускаем воркеры очереди
    await queue_manager.start()

    # Запускаем cron напоминаний о дедлайнах
    if config.REMINDER_ENABLED and config.GROUP_CHAT_ID:
        from utils.reminder import reminder_loop
        asyncio.create_task(reminder_loop(bot))

    # Устанавливаем команды бота
    await bot.set_my_commands(
        [
            {"command": "start", "description": "Запустить бота"},
            {"command": "help", "description": "Помощь"},
        ]
    )

    logger.info("Бот успешно запущен")


async def on_shutdown(bot: Bot, queue_manager: QueueManager) -> None:
    """
    Выполняется при остановке бота.

    Args:
        bot: Экземпляр бота
        queue_manager: Менеджер очереди
    """
    logger.info("Бот останавливается...")

    # Останавливаем воркеры очереди
    await queue_manager.stop()

    # Закрываем сессию бота
    await bot.session.close()

    logger.info("Бот остановлен")


async def main() -> None:
    """Основная функция запуска бота."""
    # Настраиваем логгер
    setup_logger()

    logger.info("Aspector STT v2.0 (Groq Whisper)")
    logger.info(f"Базовая директория: {config.BASE_DIR}")

    # Создаём временную директорию
    config.TEMP_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Временная директория: {config.TEMP_DIR}")

    # Инициализируем бота
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Инициализируем диспетчер
    dp = Dispatcher()

    # Создаём менеджер очереди
    queue_manager = QueueManager(bot)

    # Регистрируем middleware
    dp.message.middleware(UserRegistryMiddleware())
    dp.callback_query.middleware(UserRegistryMiddleware())

    # Регистрируем роутеры
    dp.include_router(commands_router)
    dp.include_router(contacts_router)
    dp.include_router(forwarding_router)
    dp.include_router(trello_router)
    dp.include_router(group_tasks_router)
    dp.include_router(photos_router)
    dp.include_router(voice_router)

    # Регистрируем хуки запуска/остановки
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Устанавливаем глобальный инстанс для get_queue_manager()
    import task_queue.manager as tqm
    tqm.queue_manager = queue_manager

    # Настраиваем обработку сигналов
    loop = asyncio.get_event_loop()

    def handle_signal():
        logger.info("Получен сигнал остановки")

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, handle_signal)
        except NotImplementedError:
            # Windows не поддерживает add_signal_handler для всех сигналов
            pass

    # Запускаем polling
    try:
        logger.info("Запуск polling...")
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            queue_manager=queue_manager,
        )
    except KeyboardInterrupt:
        logger.info("Поллинг остановлен пользователем")
    finally:
        await on_shutdown(bot, queue_manager)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.critical(f"Критическая ошибка: {e}")
        raise
