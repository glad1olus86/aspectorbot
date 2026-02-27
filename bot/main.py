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
from bot.handlers.language import router as language_router
from bot.handlers.photos import router as photos_router
from bot.handlers.trello import router as trello_router
from bot.handlers.user_lang import router as user_lang_router
from bot.handlers.voice import router as voice_router
from config import config
from task_queue.manager import QueueManager
from storage.pending import pending_store
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
    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # Запускаем воркеры очереди
    await queue_manager.start()

    # Устанавливаем команды бота
    await bot.set_my_commands(
        [
            {"command": "start", "description": "Запустить бота"},
            {"command": "help", "description": "Помощь"},
            {"command": "lang", "description": "Выбрать язык распознавания"},
        ]
    )

    # Запускаем периодическую очистку PendingStore
    asyncio.create_task(cleanup_pending_store())

    logger.info("Бот успешно запущен")


async def on_shutdown(bot: Bot, queue_manager: QueueManager) -> None:
    """
    Выполняется при остановке бота.

    Args:
        bot: Экземпляр бота
        queue_manager: Менеджер очереди
    """
    logger.info("Бот останавливается...")

    # Очищаем PendingStore от устаревших задач
    pending_store.cleanup_expired()

    # Останавливаем воркеры очереди
    await queue_manager.stop()

    # Закрываем сессию бота
    await bot.session.close()

    logger.info("Бот остановлен")


async def cleanup_pending_store() -> None:
    """Периодическая очистка устаревших задач из PendingStore."""
    while True:
        await asyncio.sleep(60 * config.PENDING_TTL_MINUTES)
        try:
            expired = pending_store.cleanup_expired()
            if expired:
                logger.info(f"Очищено {len(expired)} устаревших задач из PendingStore")
        except Exception as e:
            logger.error(f"Ошибка очистки PendingStore: {e}")


async def main() -> None:
    """Основная функция запуска бота."""
    # Настраиваем логгер
    setup_logger()

    logger.info("Aspector STT v1.2")
    logger.info(f"Поддерживаемые языки: {config.SUPPORTED_LANGUAGES}")
    logger.info(f"Базовая директория: {config.BASE_DIR}")

    # Создаём временную директорию
    config.TEMP_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Временная директория: {config.TEMP_DIR}")

    # Проверяем наличие моделей
    for lang_code in config.SUPPORTED_LANGUAGES.keys():
        model_path = config.get_model_path(lang_code)
        if not model_path.exists():
            logger.warning(f"Модель {lang_code} не найдена: {model_path}")
        else:
            logger.info(f"Модель {lang_code} найдена: {model_path}")

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
    dp.include_router(user_lang_router)
    dp.include_router(trello_router)
    dp.include_router(photos_router)
    dp.include_router(voice_router)
    dp.include_router(language_router)

    # Регистрируем хуки запуска/остановки
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Устанавливаем глобальный инстанс для get_queue_manager()
    import task_queue.manager as tqm
    tqm.queue_manager = queue_manager

    # Настраиваем обработку сигналов
    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    def handle_signal():
        logger.info("Получен сигнал остановки")
        stop_event.set()

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
